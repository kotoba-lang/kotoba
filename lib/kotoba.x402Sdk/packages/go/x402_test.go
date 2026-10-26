package x402

import (
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"
)

var policy = Policy{
	Networks:  []string{"base-sepolia"},
	Assets:    []string{"0x036CbD53842c5426634e7929541eC2318f3dCF7e"},
	MaxAmount: "5000",
}

func offer(mut func(*Offer)) Offer {
	o := Offer{
		Scheme: "exact", Network: "base-sepolia",
		Asset: "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
		PayTo: "0xA00366234D29d4F882088048c0B2fa0dB7302D4E",
		MaxAmountRequired: "1000", MaxTimeoutSeconds: 60,
		Extra: map[string]string{"name": "USDC", "version": "2"},
	}
	if mut != nil {
		mut(&o)
	}
	return o
}

func chal(os ...Offer) *Challenge { return &Challenge{X402Version: 1, Accepts: os} }

func TestNoPolicyPaysNothing(t *testing.T) {
	_, r := SelectOffer(chal(offer(nil)), Policy{})
	if r == nil || r.Refused != "no-policy" {
		t.Fatalf("want no-policy, got %v", r)
	}
}

func TestCheapestNotFirst(t *testing.T) {
	c := chal(offer(func(o *Offer) { o.MaxAmountRequired = "4000" }),
		offer(func(o *Offer) { o.MaxAmountRequired = "1000" }))
	got, r := SelectOffer(c, policy)
	if r != nil || got.MaxAmountRequired != "1000" {
		t.Fatalf("want the cheaper offer, got %v %v", got, r)
	}
}

func TestEveryFailingCheckIsNamed(t *testing.T) {
	c := chal(offer(func(o *Offer) {
		o.Network = "base"
		o.Asset = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
	}))
	_, r := SelectOffer(c, policy)
	if r == nil || !regexp.MustCompile(`network-not-allowed`).MatchString(r.Refused) ||
		!regexp.MustCompile(`asset-not-allowed`).MatchString(r.Refused) {
		t.Fatalf("both reasons should be named, got %v", r)
	}
}

func TestUnparseableAmountIsNotSilentlyOverBudget(t *testing.T) {
	_, r := SelectOffer(chal(offer(func(o *Offer) { o.MaxAmountRequired = "one dollar" })), policy)
	if r == nil || r.Refused != "unparseable-amount" {
		t.Fatalf("want unparseable-amount, got %v", r)
	}
}

func TestNilChallengeRefusesRatherThanPanics(t *testing.T) {
	_, r := SelectOffer(nil, policy)
	if r == nil || r.Refused != "not-a-challenge" {
		t.Fatalf("want not-a-challenge, got %v", r)
	}
}

func TestUnknownNetworkErrorsRatherThanDefaulting(t *testing.T) {
	if _, err := ChainIDFor("optimism"); err == nil {
		t.Fatal("an unknown network must not default")
	}
	if id, _ := ChainIDFor("base-sepolia"); id != 84532 {
		t.Fatal("wrong chain id")
	}
}

func TestParseChallenge(t *testing.T) {
	if ParseChallenge(500, []byte("boom")) != nil {
		t.Fatal("a 500 is not a challenge")
	}
	if ParseChallenge(402, []byte("nope")) != nil {
		t.Fatal("a 402 that is not JSON is not a challenge")
	}
}

func TestAuthorizationExpiresByTheOffersOwnTimeout(t *testing.T) {
	o := offer(func(o *Offer) { o.MaxTimeoutSeconds = 30 })
	a, err := BuildAuthorization(&o, "0xabc", 1000)
	if err != nil || a.ValidBefore != "1030" || a.ValidAfter != "0" {
		t.Fatalf("bad window: %+v %v", a, err)
	}
	if !regexp.MustCompile(`^0x[0-9a-f]{64}$`).MatchString(a.Nonce) {
		t.Fatalf("bad nonce %q", a.Nonce)
	}
}

type stubSigner struct {
	addr   string
	domain Domain
	msg    Authorization
}

func (s *stubSigner) Address() string { return s.addr }
func (s *stubSigner) SignTransferWithAuthorization(d Domain, a Authorization) (string, error) {
	s.domain, s.msg = d, a
	return "0xsig", nil
}

func TestNon402IsReturnedUntouched(t *testing.T) {
	n := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n++
		w.WriteHeader(500)
		w.Write([]byte("boom"))
	}))
	defer srv.Close()
	cl := &Client{Policy: policy, Signer: &stubSigner{addr: "0xa"}}
	status, _, body, err := cl.Fetch("GET", srv.URL, nil)
	if status != 500 || string(body) != "boom" || err != nil {
		t.Fatalf("got %d %q %v", status, body, err)
	}
	if n != 1 {
		t.Fatal("a 500 is the server's answer; do not retry over it")
	}
}

func TestMissingDomainIsRefusedNotGuessed(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(402)
		json.NewEncoder(w).Encode(chal(offer(func(o *Offer) { o.Extra = nil })))
	}))
	defer srv.Close()
	cl := &Client{Policy: policy, Signer: &stubSigner{addr: "0xa"}}
	_, _, _, err := cl.Fetch("GET", srv.URL, nil)
	if err == nil || !regexp.MustCompile(`EIP-712`).MatchString(err.Error()) {
		t.Fatalf("want an EIP-712 refusal, got %v", err)
	}
}

func TestSignerGetsTheOffersOwnDomain(t *testing.T) {
	var echoed string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if h := r.Header.Get("X-PAYMENT"); h != "" {
			echoed = h
			w.WriteHeader(200)
			w.Write([]byte("paid"))
			return
		}
		w.WriteHeader(402)
		json.NewEncoder(w).Encode(chal(offer(nil)))
	}))
	defer srv.Close()
	s := &stubSigner{addr: "0xdeadbeef"}
	cl := &Client{Policy: policy, Signer: s, Now: func() int64 { return 1000 }}
	status, _, body, err := cl.Fetch("GET", srv.URL, nil)
	if err != nil || status != 200 || string(body) != "paid" {
		t.Fatalf("got %d %q %v", status, body, err)
	}
	if s.domain.Name != "USDC" || s.domain.ChainID != 84532 ||
		s.domain.VerifyingContract != offer(nil).Asset || s.msg.From != "0xdeadbeef" {
		t.Fatalf("the signer must get the offer's own domain, got %+v", s.domain)
	}
	raw, _ := base64.StdEncoding.DecodeString(echoed)
	var sent map[string]any
	json.Unmarshal(raw, &sent)
	if sent["scheme"] != "exact" {
		t.Fatalf("wrong scheme on the wire: %v", sent)
	}
}

func TestUserAgentIsSet(t *testing.T) {
	var ua string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ua = r.Header.Get("User-Agent")
		w.WriteHeader(200)
	}))
	defer srv.Close()
	cl := &Client{Policy: policy, Signer: &stubSigner{addr: "0xa"}}
	cl.Fetch("GET", srv.URL, nil)
	if !regexp.MustCompile(`x402-sdk-go`).MatchString(ua) {
		t.Fatalf("a default agent gets 403 from some edges; got %q", ua)
	}
}
