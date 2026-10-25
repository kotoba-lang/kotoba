// Command tls_peer is a Storj TLS peer built out of storj.io/common's own
// tlsopts, so that a handshake with it is evidence rather than a rehearsal.
//
// Everywhere else in this repo the reference implementation produces bytes and
// the .cljc asserts it reads them the same way, or the .cljc produces files
// and the reference implementation is asked to load them. This goes further:
// both sides run at once and have to agree, during a live mutual-TLS
// handshake, about who the other one is.
//
//	go run tls_peer.go -serve -identity /tmp/id-go -port 0
//	go run tls_peer.go -dial 127.0.0.1:9000 -identity /tmp/id-go -expect <hex>
//
// In serve mode it prints `listening <port>` as soon as the socket is bound,
// so a caller can wait for that line instead of sleeping, then accepts one
// connection, prints the peer's node ID and exits.
package main

import (
	"context"
	"crypto/tls"
	"encoding/hex"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"path/filepath"
	"strings"

	"storj.io/common/identity"
	"storj.io/common/pb"
	"storj.io/common/peertls/tlsopts"
	"storj.io/common/storj"
	"storj.io/drpc"
	"storj.io/drpc/drpcconn"
	"storj.io/drpc/drpcserver"
)

// checkInRPC is read from storj.io/common's own DRPC description rather than
// written here. This file had "/node.Node/CheckIn" hardcoded, the library had
// the same string, and a test compared the two — three copies of one guess,
// which a real satellite rejected as an unknown rpc. Deriving it means this
// harness cannot agree with a mistake.
var checkInRPC = func() string {
	d := pb.DRPCNodeDescription{}
	for i := 0; i < d.NumMethods(); i++ {
		if rpc, _, _, _, ok := d.Method(i); ok && strings.HasSuffix(rpc, "/CheckIn") {
			return rpc
		}
	}
	panic("no CheckIn method in pb.DRPCNodeDescription")
}()

// greeting is exchanged after the handshake so that both peers have to finish
// it, rather than one of them merely believing it did.
const greeting = "storj\n"

func loadIdentity(dir string) *identity.FullIdentity {
	cfg := identity.Config{
		CertPath: filepath.Join(dir, "identity.cert"),
		KeyPath:  filepath.Join(dir, "identity.key"),
	}
	ident, err := cfg.Load()
	if err != nil {
		fmt.Printf("FAIL loading identity from %s: %v\n", dir, err)
		os.Exit(1)
	}
	return ident
}

func options(ident *identity.FullIdentity) *tlsopts.Options {
	// UsePeerCAWhitelist stays false: these identities are self-signed by
	// whoever minted them, exactly as a storage node's is, and Storj's
	// production whitelist would — correctly — refuse every one of them.
	opts, err := tlsopts.NewOptions(ident, tlsopts.Config{
		PeerIDVersions: "0",
	}, nil)
	if err != nil {
		fmt.Printf("FAIL tlsopts.NewOptions: %v\n", err)
		os.Exit(1)
	}
	return opts
}

func peerID(state tls.ConnectionState) (storj.NodeID, error) {
	peer, err := identity.PeerIdentityFromChain(state.PeerCertificates)
	if err != nil {
		return storj.NodeID{}, err
	}
	return peer.ID, nil
}

func main() {
	serve := flag.Bool("serve", false, "accept one connection and report the peer")
	drpcMode := flag.Bool("drpc", false, "serve DRPC over the TLS listener instead of a greeting")
	dial := flag.String("dial", "", "host:port to connect to")
	dir := flag.String("identity", "", "identity directory")
	port := flag.Int("port", 0, "port to listen on, 0 for any")
	expect := flag.String("expect", "", "hex node id the peer must present")
	rpcName := flag.String("rpc", "", "with -dial, make this rpc over the connection")
	payload := flag.String("payload", "", "hex request body for -rpc")
	flag.Parse()

	if *dir == "" {
		fmt.Println("FAIL -identity is required")
		os.Exit(1)
	}
	ident := loadIdentity(*dir)
	opts := options(ident)

	switch {
	case *serve && *drpcMode:
		doServeDRPC(opts, *port)
	case *serve:
		doServe(opts, *port, *expect)
	case *dial != "" && *rpcName != "":
		doRPC(opts, *dial, *expect, *rpcName, *payload)
	case *dial != "":
		doDial(opts, *dial, *expect)
	default:
		fmt.Println("FAIL one of -serve or -dial is required")
		os.Exit(1)
	}
}

func doServe(opts *tlsopts.Options, port int, expect string) {
	listener, err := tls.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port), opts.ServerTLSConfig())
	if err != nil {
		fmt.Printf("FAIL listen: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("listening %d\n", listener.Addr().(*net.TCPAddr).Port)
	os.Stdout.Sync()

	conn, err := listener.Accept()
	if err != nil {
		fmt.Printf("FAIL accept: %v\n", err)
		os.Exit(1)
	}
	defer func() { _ = conn.Close() }()

	// Accept returns before the handshake; without forcing it here a refused
	// peer would look like a successful connection that later went quiet.
	tlsConn := conn.(*tls.Conn)
	if err := tlsConn.Handshake(); err != nil {
		fmt.Printf("FAIL handshake: %v\n", err)
		os.Exit(1)
	}
	report(tlsConn.ConnectionState(), expect)

	// A completed handshake is not the same claim as a usable connection, and
	// on TLS 1.3 a client that hangs up right after its own Finished can leave
	// the server reporting EOF while the client reports success. So the server
	// writes and the client reads: whichever side is asked afterwards, both
	// had to get all the way through.
	if _, err := tlsConn.Write([]byte(greeting)); err != nil {
		fmt.Printf("FAIL write: %v\n", err)
		os.Exit(1)
	}
	buf := make([]byte, len(greeting))
	if _, err := io.ReadFull(tlsConn, buf); err != nil {
		fmt.Printf("FAIL read back: %v\n", err)
		os.Exit(1)
	}
	if string(buf) != greeting {
		fmt.Printf("FAIL echo mismatch: %q\n", string(buf))
		os.Exit(1)
	}
	fmt.Println("ok   application data flowed both ways")
}

// raw is a drpc.Message that is its own bytes, and rawEncoding passes them
// through. No generated code: drpc.Handler is one method and drpc.Encoding is
// two, so a byte-passing encoding answers a unary call without protoc.
type raw struct{ data []byte }

// raw2 and rawEncoding2 are the client-side pair; the server-side ones above
// are used by the handler and keeping them separate avoids a name collision
// that would make the two directions look like one.
type raw2 struct{ data []byte }

type rawEncoding2 struct{}

func (rawEncoding2) Marshal(msg drpc.Message) ([]byte, error) { return msg.(*raw2).data, nil }

func (rawEncoding2) Unmarshal(buf []byte, msg drpc.Message) error {
	m := msg.(*raw2)
	m.data = append([]byte(nil), buf...)
	return nil
}

type rawEncoding struct{}

func (rawEncoding) Marshal(msg drpc.Message) ([]byte, error) { return msg.(*raw).data, nil }

func (rawEncoding) Unmarshal(buf []byte, msg drpc.Message) error {
	m := msg.(*raw)
	m.data = append([]byte(nil), buf...)
	return nil
}

// echo answers with `<rpc>:<request>`, so a passing test proves the rpc name
// was routed rather than that some bytes came back.
type echo struct{}

func (echo) HandleRPC(stream drpc.Stream, rpc string) error {
	var in raw
	if err := stream.MsgRecv(&in, rawEncoding{}); err != nil {
		return err
	}
	fmt.Printf("rpc %s (%d bytes)\n", rpc, len(in.data))

	// The real thing, for the one rpc a node cannot skip: parse the request
	// with storj.io/common's own generated code and answer with a real
	// CheckInResponse. A client that gets this back has had its request
	// understood by a satellite's parser, not merely echoed.
	if rpc == checkInRPC {
		var req pb.CheckInRequest
		if err := pb.Unmarshal(in.data, &req); err != nil {
			return err
		}
		fmt.Printf("check-in address=%q version=%q free-disk=%d email=%q\n",
			req.Address, req.Version.Version, req.Capacity.FreeDisk, req.Operator.Email)

		// Refuse when the node claims an address nobody could dial, so the
		// interesting case is reachable from a test: a call that worked and an
		// introduction that did not.
		resp := &pb.CheckInResponse{PingNodeSuccess: true, PingNodeSuccessQuic: true}
		if req.Address == "" || strings.HasPrefix(req.Address, "0.0.0.0") {
			resp = &pb.CheckInResponse{
				PingNodeSuccess:  false,
				PingErrorMessage: "failed to dial storage node at address " + req.Address,
			}
		}
		out, err := pb.Marshal(resp)
		if err != nil {
			return err
		}
		return stream.MsgSend(&raw{data: out}, rawEncoding{})
	}

	out := raw{data: append([]byte(rpc+":"), in.data...)}
	return stream.MsgSend(&out, rawEncoding{})
}

// doServeDRPC is the whole stack on the reference side: Storj's mutual TLS
// underneath, Storj's DRPC on top. A client that gets an answer out of this
// has done every step a real node does before it says anything.
func doServeDRPC(opts *tlsopts.Options, port int) {
	listener, err := tls.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", port), opts.ServerTLSConfig())
	if err != nil {
		fmt.Printf("FAIL listen: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("listening %d\n", listener.Addr().(*net.TCPAddr).Port)
	_ = os.Stdout.Sync()

	if err := drpcserver.New(echo{}).Serve(context.Background(), listener); err != nil {
		fmt.Printf("serve ended: %v\n", err)
	}
}

func doDial(opts *tlsopts.Options, addr, expect string) {
	var cfg *tls.Config
	if expect != "" {
		raw, err := hex.DecodeString(expect)
		if err != nil {
			fmt.Printf("FAIL bad -expect: %v\n", err)
			os.Exit(1)
		}
		var id storj.NodeID
		copy(id[:], raw)
		// ClientTLSConfig adds the check that the peer is the node that was
		// asked for — the same thing storj.node.tls does with
		// :expected-node-id, and the reason a man in the middle cannot simply
		// present a valid chain of its own.
		cfg = opts.ClientTLSConfig(id)
	} else {
		cfg = opts.UnverifiedClientTLSConfig()
	}

	conn, err := tls.Dial("tcp", addr, cfg)
	if err != nil {
		fmt.Printf("FAIL dial: %v\n", err)
		os.Exit(1)
	}
	defer func() { _ = conn.Close() }()
	report(conn.ConnectionState(), "")

	buf := make([]byte, len(greeting))
	if _, err := io.ReadFull(conn, buf); err != nil {
		fmt.Printf("FAIL read: %v\n", err)
		os.Exit(1)
	}
	if string(buf) != greeting {
		fmt.Printf("FAIL greeting mismatch: %q\n", string(buf))
		os.Exit(1)
	}
	if _, err := conn.Write(buf); err != nil {
		fmt.Printf("FAIL echo: %v\n", err)
		os.Exit(1)
	}
	fmt.Println("ok   application data flowed both ways")
}

// doRPC is the whole stack from the reference side: Storj mutual TLS, then a
// real drpcconn.Conn making a real call. A node that answers this has been
// asked a question the way a satellite asks one.
func doRPC(opts *tlsopts.Options, addr, expect, rpcName, payloadHex string) {
	var cfg *tls.Config
	if expect != "" {
		raw, err := hex.DecodeString(expect)
		if err != nil {
			fmt.Printf("FAIL bad -expect: %v\n", err)
			os.Exit(1)
		}
		var id storj.NodeID
		copy(id[:], raw)
		cfg = opts.ClientTLSConfig(id)
	} else {
		cfg = opts.UnverifiedClientTLSConfig()
	}

	conn, err := tls.Dial("tcp", addr, cfg)
	if err != nil {
		fmt.Printf("FAIL dial: %v\n", err)
		os.Exit(1)
	}
	defer func() { _ = conn.Close() }()
	report(conn.ConnectionState(), "")

	body, err := hex.DecodeString(payloadHex)
	if err != nil {
		fmt.Printf("FAIL bad -payload: %v\n", err)
		os.Exit(1)
	}

	client := drpcconn.New(conn)
	defer func() { _ = client.Close() }()

	var out raw2
	if err := client.Invoke(context.Background(), rpcName, rawEncoding2{},
		&raw2{data: body}, &out); err != nil {
		fmt.Printf("FAIL invoke %s: %v\n", rpcName, err)
		os.Exit(1)
	}
	fmt.Printf("ok   %s answered %d bytes\n", rpcName, len(out.data))
	fmt.Printf("response %s\n", hex.EncodeToString(out.data))
}

func report(state tls.ConnectionState, expect string) {
	id, err := peerID(state)
	if err != nil {
		fmt.Printf("FAIL peer identity: %v\n", err)
		os.Exit(1)
	}
	got := hex.EncodeToString(id.Bytes())
	if expect != "" && got != expect {
		fmt.Printf("FAIL peer id %s, expected %s\n", got, expect)
		os.Exit(1)
	}
	fmt.Printf("ok   handshake complete, peer %s\n", got)
	fmt.Printf("peer %s\n", got)
}
