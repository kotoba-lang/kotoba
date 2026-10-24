// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.28;

/// @notice Non-authoritative receipts for opaque Kotobase checkpoints.
/// @dev Database identifiers, logical roots, physical roots and tenant data
///      must be hashed off-chain with a deployment-specific disclosure salt.
contract KotobaseCheckpointAnchor {
    error ZeroIdempotencyKey();
    error ZeroCheckpointDigest();
    error IdempotencyConflict(bytes32 existingDigest, bytes32 suppliedDigest);

    struct Receipt {
        bytes32 checkpointDigest;
        uint64 anchoredAt;
    }

    mapping(bytes32 idempotencyKey => Receipt receipt) public receipts;

    event CheckpointAnchored(
        bytes32 indexed idempotencyKey,
        bytes32 indexed checkpointDigest
    );

    /// @return created False when an identical retry already exists.
    function anchor(bytes32 idempotencyKey, bytes32 checkpointDigest)
        external
        returns (bool created)
    {
        if (idempotencyKey == bytes32(0)) revert ZeroIdempotencyKey();
        if (checkpointDigest == bytes32(0)) revert ZeroCheckpointDigest();

        Receipt storage existing = receipts[idempotencyKey];
        if (existing.checkpointDigest != bytes32(0)) {
            if (existing.checkpointDigest != checkpointDigest) {
                revert IdempotencyConflict(existing.checkpointDigest, checkpointDigest);
            }
            return false;
        }

        receipts[idempotencyKey] = Receipt({
            checkpointDigest: checkpointDigest,
            anchoredAt: uint64(block.timestamp)
        });
        emit CheckpointAnchored(idempotencyKey, checkpointDigest);
        return true;
    }
}
