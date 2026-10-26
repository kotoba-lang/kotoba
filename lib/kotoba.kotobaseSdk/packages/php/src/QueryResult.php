<?php

declare(strict_types=1);

namespace NetKotobase;

final class QueryResult
{
    /** @param array<string, mixed> $meta @param list<string> $warnings */
    public function __construct(
        public readonly string $language,
        public readonly mixed $data,
        public readonly array $meta,
        public readonly array $warnings = [],
    ) {}
}
