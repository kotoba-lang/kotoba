//go:build ignore

// gen_rpc_paths.go — the DRPC paths this library uses, printed from Storj's
// own generated code.
//
// Every other fixture here is bytes checked against storj.io/common. The
// *names* those bytes travel under were not: they were typed into a constant
// and then typed again into a test, which is a check that the same guess was
// made twice. It passed for weeks with "/node.Node/CheckIn", and a real
// satellite answered `protocol error: unknown rpc: "/node.Node/CheckIn"`.
//
//	go run gen_rpc_paths.go            # print
//	go run gen_rpc_paths.go -verify    # compare against rpc-paths.txt
//
// The paths come from the DRPC description objects, which are what the server
// actually routes on — not from a string in this file.
package main

import (
	"flag"
	"fmt"
	"os"
	"sort"
	"strings"

	"storj.io/common/pb"
	"storj.io/drpc"
)

// every description this library speaks to, and the ones it serves
func descriptions() []drpc.Description {
	return []drpc.Description{
		pb.DRPCNodeDescription{},       // contact.Node — node → satellite
		pb.DRPCContactDescription{},    // contact.Contact — satellite → node
		pb.DRPCPiecestoreDescription{}, // piecestore.Piecestore
	}
}

func paths() []string {
	var out []string
	for _, d := range descriptions() {
		for i := 0; i < d.NumMethods(); i++ {
			rpc, _, _, _, ok := d.Method(i)
			if !ok {
				continue
			}
			out = append(out, rpc)
		}
	}
	sort.Strings(out)
	return out
}

func main() {
	verify := flag.Bool("verify", false, "compare against rpc-paths.txt")
	flag.Parse()

	got := strings.Join(paths(), "\n") + "\n"

	if !*verify {
		fmt.Print(got)
		return
	}

	want, err := os.ReadFile("rpc-paths.txt")
	if err != nil {
		fmt.Fprintln(os.Stderr, "read rpc-paths.txt:", err)
		os.Exit(1)
	}
	if string(want) != got {
		fmt.Fprintln(os.Stderr, "rpc-paths.txt is stale.\n--- checked in ---")
		fmt.Fprint(os.Stderr, string(want))
		fmt.Fprintln(os.Stderr, "--- storj.io/common says ---")
		fmt.Fprint(os.Stderr, got)
		os.Exit(1)
	}
	fmt.Println("ok   rpc-paths.txt matches storj.io/common")
}
