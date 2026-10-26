// Package x402 is an x402 client: read the 402, pay, retry.
//
// The loop is four HTTP steps and this package owns three of them. Signing is
// injected, so it holds no key and imports no cryptography: the wallet stays
// wherever its owner put it. A payment library that wants your key is a place
// your key can leak from.
//
// See ../../spec/wire.md for the contract every package here implements.
package x402

import (
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"net/http"
	"sort"
	"strings"
	"time"
)

// UserAgent is sent by the default client.
//
// Go's http.Client sends "Go-http-client/..." and Cloudflare answers 403 to
// some default agents. Measured 2026-09-01: Python's urllib default is
// rejected by x402.nexus outright. An SDK that cannot reach the facilitator it
// is written for is not an SDK, and that failure arrives looking like
// authorisation rather than like a bot rule.
const UserAgent = "x402-sdk-go/0.1.0 (+https://github.com/kotoba-lang/x402-sdk)"

// Offer is one acceptable payment, stated completely by the seller.
type Offer struct {
	Scheme             string            `json:"scheme"`
	Network            string            `json:"network"`
	Asset              string            `json:"asset"`
	PayTo              string            `json:"payTo"`
	MaxAmountRequired  string            `json:"maxAmountRequired"`
	MaxTimeoutSeconds  int               `json:"maxTimeoutSeconds"`
	Resource           string            `json:"resource,omitempty"`
	Description        string            `json:"description,omitempty"`
	// Extra carries the EIP-712 domain of Asset on Network. Never a constant.
	Extra map[string]string `json:"extra,omitempty"`
}

// Challenge is a 402 body.
type Challenge struct {
	X402Version int     `json:"x402Version"`
	Accepts     []Offer `json:"accepts"`
	Error       string  `json:"error,omitempty"`
}

// Policy is what this buyer will pay. Every field is required: a buyer with an
// empty policy pays anything, and a default ceiling is a limit nobody chose.
type Policy struct {
	Networks  []string
	Assets    []string
	MaxAmount string
	Schemes   []string // empty means exact and transaction
}

// Authorization is the EIP-3009 message the buyer signs.
type Authorization struct {
	From        string `json:"from"`
	To          string `json:"to"`
	Value       string `json:"value"`
	ValidAfter  string `json:"validAfter"`
	ValidBefore string `json:"validBefore"`
	Nonce       string `json:"nonce"`
}

// Domain is the EIP-712 domain, built from the offer.
type Domain struct {
	Name              string `json:"name"`
	Version           string `json:"version"`
	ChainID           int    `json:"chainId"`
	VerifyingContract string `json:"verifyingContract"`
}

// Signer is supplied by the caller. The key never enters this package.
type Signer interface {
	Address() string
	SignTransferWithAuthorization(Domain, Authorization) (string, error)
}

// Refusal is a policy decision, distinct from a transport error.
type Refusal struct {
	Refused string
	Detail  string
}

func (r *Refusal) Error() string { return r.Refused + ": " + r.Detail }

var chainIDs = map[string]int{
	"base": 8453, "base-sepolia": 84532,
	"eip155:8453": 8453, "eip155:84532": 84532,
}

// ChainIDFor returns the chain id for a network, or an error.
//
// Never a default: a wrong chainId in an EIP-712 domain makes a valid
// signature recover a different address, and the payment is rejected as a bad
// signature -- which reads like the buyer's fault.
func ChainIDFor(network string) (int, error) {
	id, ok := chainIDs[network]
	if !ok {
		return 0, fmt.Errorf("x402: unknown network %q", network)
	}
	return id, nil
}

// ParseChallenge reads a 402 body. It returns nil for anything that is not a
// challenge, which a caller must be able to tell from a challenge with nothing
// usable in it.
func ParseChallenge(status int, body []byte) *Challenge {
	if status != http.StatusPaymentRequired {
		return nil
	}
	var c Challenge
	if err := json.Unmarshal(body, &c); err != nil || c.Accepts == nil {
		return nil
	}
	return &c
}

// SelectOffer returns the cheapest offer the policy allows, or a Refusal.
//
// NOT accepts[0]. Sellers list the same resource on mainnet and on a testnet
// in their own order, and taking the first is how a buyer pays real money to
// rehearse.
//
// Every failing check is recorded, not just the first: an offer on the wrong
// network usually names that network's token too, and a caller told only
// network-not-allowed will fix the network and be refused again.
func SelectOffer(c *Challenge, p Policy) (*Offer, *Refusal) {
	if c == nil {
		return nil, &Refusal{"not-a-challenge", "the response was not a 402 x402 challenge"}
	}
	if len(p.Networks) == 0 || len(p.Assets) == 0 || p.MaxAmount == "" {
		return nil, &Refusal{"no-policy", "a buyer without a policy would pay anything"}
	}
	schemes := p.Schemes
	if len(schemes) == 0 {
		schemes = []string{"exact", "transaction"}
	}
	max, ok := new(big.Int).SetString(p.MaxAmount, 10)
	if !ok {
		return nil, &Refusal{"bad-policy", "maxAmount is not a decimal integer"}
	}

	reasons := map[string]bool{}
	var allowed []Offer
	for _, o := range c.Accepts {
		var fail []string
		if !contains(schemes, o.Scheme) {
			fail = append(fail, "scheme-not-allowed")
		}
		if !contains(p.Networks, o.Network) {
			fail = append(fail, "network-not-allowed")
		}
		if !containsFold(p.Assets, o.Asset) {
			fail = append(fail, "asset-not-allowed")
		}
		if amt, ok := new(big.Int).SetString(o.MaxAmountRequired, 10); !ok {
			fail = append(fail, "unparseable-amount")
		} else if amt.Cmp(max) > 0 {
			fail = append(fail, "over-budget")
		}
		for _, f := range fail {
			reasons[f] = true
		}
		if len(fail) == 0 {
			allowed = append(allowed, o)
		}
	}
	if len(allowed) == 0 {
		keys := make([]string, 0, len(reasons))
		for k := range reasons {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		why := "no-offers"
		if len(keys) > 0 {
			why = strings.Join(keys, "+")
		}
		return nil, &Refusal{why, fmt.Sprintf("none of %d offer(s) satisfied the policy", len(c.Accepts))}
	}
	sort.SliceStable(allowed, func(i, j int) bool {
		a, _ := new(big.Int).SetString(allowed[i].MaxAmountRequired, 10)
		b, _ := new(big.Int).SetString(allowed[j].MaxAmountRequired, 10)
		return a.Cmp(b) < 0
	})
	return &allowed[0], nil
}

func contains(xs []string, x string) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}

func containsFold(xs []string, x string) bool {
	for _, v := range xs {
		if strings.EqualFold(v, x) {
			return true
		}
	}
	return false
}

// RandomNonce returns a 32-byte hex nonce.
func RandomNonce() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return "0x" + hex.EncodeToString(b), nil
}

// BuildAuthorization builds the EIP-3009 message for an offer.
func BuildAuthorization(o *Offer, from string, now int64) (Authorization, error) {
	nonce, err := RandomNonce()
	if err != nil {
		return Authorization{}, err
	}
	ttl := o.MaxTimeoutSeconds
	if ttl == 0 {
		ttl = 60
	}
	return Authorization{
		From: from, To: o.PayTo, Value: o.MaxAmountRequired,
		ValidAfter: "0", ValidBefore: fmt.Sprint(now + int64(ttl)), Nonce: nonce,
	}, nil
}

// EncodePaymentHeader base64-encodes the X-PAYMENT payload.
func EncodePaymentHeader(v any) (string, error) {
	b, err := json.Marshal(v)
	if err != nil {
		return "", err
	}
	return base64.StdEncoding.EncodeToString(b), nil
}

// Client performs the loop.
type Client struct {
	Policy Policy
	Signer Signer
	HTTP   *http.Client
	Now    func() int64
}

func (cl *Client) httpClient() *http.Client {
	if cl.HTTP != nil {
		return cl.HTTP
	}
	return &http.Client{Timeout: 30 * time.Second}
}

func (cl *Client) now() int64 {
	if cl.Now != nil {
		return cl.Now()
	}
	return time.Now().Unix()
}

func (cl *Client) do(req *http.Request) (int, http.Header, []byte, error) {
	req.Header.Set("User-Agent", UserAgent)
	res, err := cl.httpClient().Do(req)
	if err != nil {
		return 0, nil, nil, err
	}
	defer res.Body.Close()
	b, err := io.ReadAll(res.Body)
	return res.StatusCode, res.Header, b, err
}

// Challenge asks what a resource costs, without paying. No key, no payment, no
// side effect on the seller: the safe first call.
func (cl *Client) Challenge(url string) (*Challenge, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	status, _, body, err := cl.do(req)
	if err != nil {
		return nil, err
	}
	return ParseChallenge(status, body), nil
}

// Fetch retrieves a resource, paying if it asks.
//
// A non-402 response is returned untouched -- including errors, because a 500
// is the server's answer and swallowing it to retry would hide it.
func (cl *Client) Fetch(method, url string, body []byte) (int, http.Header, []byte, error) {
	req, err := newRequest(method, url, body)
	if err != nil {
		return 0, nil, nil, err
	}
	status, hdr, resBody, err := cl.do(req)
	if err != nil {
		return status, hdr, resBody, err
	}
	c := ParseChallenge(status, resBody)
	if c == nil {
		return status, hdr, resBody, nil
	}

	offer, refusal := SelectOffer(c, cl.Policy)
	if refusal != nil {
		return status, hdr, resBody, refusal
	}
	if offer.Scheme != "exact" {
		return status, hdr, resBody, fmt.Errorf(
			"x402: this client signs the 'exact' scheme; the offer asks for %q, "+
				"which needs a transfer this package does not make", offer.Scheme)
	}
	name, version := offer.Extra["name"], offer.Extra["version"]
	if name == "" || version == "" {
		return status, hdr, resBody, fmt.Errorf(
			"x402: the offer carries no EIP-712 domain (extra.name/version); signing " +
				"under a guessed one recovers a different address and is rejected as a bad signature")
	}
	chainID, err := ChainIDFor(offer.Network)
	if err != nil {
		return status, hdr, resBody, err
	}
	auth, err := BuildAuthorization(offer, cl.Signer.Address(), cl.now())
	if err != nil {
		return status, hdr, resBody, err
	}
	sig, err := cl.Signer.SignTransferWithAuthorization(
		Domain{name, version, chainID, offer.Asset}, auth)
	if err != nil {
		return status, hdr, resBody, err
	}
	header, err := EncodePaymentHeader(map[string]any{
		"x402Version": c.X402Version, "scheme": "exact", "network": offer.Network,
		"payload": map[string]any{"signature": sig, "authorization": auth},
	})
	if err != nil {
		return status, hdr, resBody, err
	}
	req2, err := newRequest(method, url, body)
	if err != nil {
		return status, hdr, resBody, err
	}
	req2.Header.Set("X-PAYMENT", header)
	return cl.do(req2)
}

func newRequest(method, url string, body []byte) (*http.Request, error) {
	if body == nil {
		return http.NewRequest(method, url, nil)
	}
	return http.NewRequest(method, url, strings.NewReader(string(body)))
}
