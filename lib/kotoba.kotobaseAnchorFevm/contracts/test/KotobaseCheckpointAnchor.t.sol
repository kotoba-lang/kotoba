// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.28;

import {KotobaseCheckpointAnchor} from "../src/KotobaseCheckpointAnchor.sol";

contract KotobaseCheckpointAnchorTest {
    KotobaseCheckpointAnchor private anchorContract;

    function setUp() public {
        anchorContract = new KotobaseCheckpointAnchor();
    }

    function testStoresOnlyOpaqueReceipt() public {
        bytes32 key = keccak256("request-1");
        bytes32 digest = keccak256("private-checkpoint");
        bool created = anchorContract.anchor(key, digest);
        (bytes32 stored, uint64 anchoredAt) = anchorContract.receipts(key);
        require(created && stored == digest && anchoredAt > 0, "receipt mismatch");
    }

    function testIdenticalRetryIsNoOp() public {
        bytes32 key = keccak256("request-1");
        bytes32 digest = keccak256("checkpoint");
        require(anchorContract.anchor(key, digest), "first call must create");
        require(!anchorContract.anchor(key, digest), "retry must be idempotent");
    }

    function testConflictingRetryReverts() public {
        bytes32 key = keccak256("request-1");
        anchorContract.anchor(key, keccak256("a"));
        try anchorContract.anchor(key, keccak256("b")) {
            revert("conflict accepted");
        } catch {}
    }

    function testZeroValuesRevert() public {
        try anchorContract.anchor(bytes32(0), keccak256("a")) { revert("zero key accepted"); }
        catch {}
        try anchorContract.anchor(keccak256("key"), bytes32(0)) { revert("zero digest accepted"); }
        catch {}
    }
}
