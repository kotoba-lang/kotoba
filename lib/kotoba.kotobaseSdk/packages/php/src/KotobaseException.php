<?php

declare(strict_types=1);

namespace NetKotobase;

final class KotobaseException extends \RuntimeException
{
    public function __construct(
        string $message,
        public readonly string $errorCode = 'query_failed',
        public readonly int $status = 0,
        public readonly bool $retryable = false,
        public readonly ?string $requestId = null,
        public readonly mixed $details = null,
    ) {
        parent::__construct($message);
    }
}
