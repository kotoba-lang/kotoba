<?php

declare(strict_types=1);

namespace NetKotobase;

final class KotobaseClient
{
    private const QUERY_PATH = '/xrpc/ai.gftd.apps.kotobase.query.execute';

    /**
     * Transport receives (url, headers, JSON body, timeout seconds) and returns
     * [HTTP status, response body].
     *
     * @param null|callable(string, array<string,string>, string, float): array{int,string} $transport
     * @param array<string,string> $headers
     */
    public function __construct(
        private readonly string $endpoint = 'https://kotobase.net',
        private readonly ?string $token = null,
        private readonly mixed $transport = null,
        private readonly array $headers = [],
        private readonly float $timeout = 30.0,
    ) {}

    /** @param array<string,mixed> $request */
    public function query(array $request, ?string $requestId = null): QueryResult
    {
        self::validateRequest($request);
        $headers = [
            'accept' => 'application/json',
            'content-type' => 'application/json',
            ...$this->headers,
        ];
        if ($this->token !== null && $this->token !== '') {
            $headers['authorization'] = 'Bearer ' . $this->token;
        }
        if ($requestId !== null && $requestId !== '') {
            $headers['x-request-id'] = $requestId;
        }

        $body = json_encode($request, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        $transport = $this->transport ?? self::curlTransport(...);
        try {
            [$status, $responseBody] = $transport(
                rtrim($this->endpoint, '/') . self::QUERY_PATH,
                $headers,
                $body,
                $this->timeout,
            );
        } catch (KotobaseException $error) {
            throw $error;
        } catch (\Throwable $error) {
            throw new KotobaseException($error->getMessage(), 'transport_error', retryable: true);
        }

        try {
            $decoded = json_decode($responseBody, true, flags: JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new KotobaseException(
                'Kotobase returned a non-JSON response',
                'invalid_response',
                $status,
                $status >= 500,
            );
        }
        if ($status < 200 || $status >= 300) {
            throw self::responseError($status, $decoded);
        }
        if (!is_array($decoded)
            || ($decoded['ok'] ?? null) !== true
            || !is_string($decoded['language'] ?? null)
            || !array_key_exists('data', $decoded)
            || !is_array($decoded['meta'] ?? null)
            || !is_string($decoded['meta']['requestId'] ?? null)
            || !is_int($decoded['meta']['elapsedMs'] ?? null)) {
            throw new KotobaseException(
                'Kotobase returned an invalid query result',
                'invalid_response',
                $status,
            );
        }
        return new QueryResult(
            $decoded['language'],
            $decoded['data'],
            $decoded['meta'],
            is_array($decoded['warnings'] ?? null) ? $decoded['warnings'] : [],
        );
    }

    /** @param array<string,mixed> $options */
    public function datalog(string $query, array $options = []): QueryResult
    {
        return $this->textQuery('datalog', $query, $options);
    }

    /** @param array<string,mixed> $options */
    public function cypher(string $query, array $options = []): QueryResult
    {
        return $this->textQuery('cypher', $query, $options);
    }

    /** @param array<string,mixed> $options */
    public function graphql(string $query, array $options = []): QueryResult
    {
        return $this->textQuery('graphql', $query, $options);
    }

    /** @param array<string,mixed> $options */
    public function graphdb(string $query, array $options = []): QueryResult
    {
        return $this->textQuery('graphdb', $query, $options);
    }

    /** @param array<string,mixed> $options */
    public function sparql(string $query, array $options = []): QueryResult
    {
        return $this->textQuery('sparql', $query, $options);
    }

    /** @param list<list<mixed>> $bytecode @param array<string,mixed> $options */
    public function gremlin(array $bytecode, array $options = []): QueryResult
    {
        return $this->languageQuery('gremlin', $bytecode, $options);
    }

    /** @param array<string,mixed> $options */
    private function textQuery(string $language, string $query, array $options): QueryResult
    {
        return $this->languageQuery($language, $query, $options);
    }

    /** @param array<string,mixed> $options */
    private function languageQuery(string $language, mixed $query, array $options): QueryResult
    {
        $request = ['language' => $language, 'query' => $query];
        foreach (['parameters', 'database', 'collections', 'options'] as $key) {
            if (array_key_exists($key, $options)) {
                $request[$key] = $options[$key];
            }
        }
        return $this->query($request, $options['requestId'] ?? null);
    }

    /** @param array<string,mixed> $request */
    private static function validateRequest(array $request): void
    {
        $languages = ['datalog', 'cypher', 'gremlin', 'graphdb', 'graphql', 'sparql'];
        $language = $request['language'] ?? null;
        $query = $request['query'] ?? null;
        if (!is_string($language) || !in_array($language, $languages, true)) {
            throw new \InvalidArgumentException('unsupported query language');
        }
        if ($language === 'gremlin') {
            if (!is_array($query) || $query === []) {
                throw new \InvalidArgumentException('Gremlin query must be non-empty bytecode');
            }
        } elseif (!is_string($query) || trim($query) === '') {
            throw new \InvalidArgumentException($language . ' query must be a non-empty string');
        }
    }

    private static function responseError(int $status, mixed $decoded): KotobaseException
    {
        $error = is_array($decoded) && is_array($decoded['error'] ?? null)
            ? $decoded['error'] : [];
        return new KotobaseException(
            is_string($error['message'] ?? null) ? $error['message'] : "Kotobase query failed with HTTP {$status}",
            is_string($error['code'] ?? null) ? $error['code'] : 'query_failed',
            $status,
            is_bool($error['retryable'] ?? null) ? $error['retryable'] : $status >= 500,
            is_string($error['requestId'] ?? null) ? $error['requestId'] : null,
            $error['details'] ?? null,
        );
    }

    /** @param array<string,string> $headers @return array{int,string} */
    private static function curlTransport(string $url, array $headers, string $body, float $timeout): array
    {
        $handle = curl_init($url);
        if ($handle === false) {
            throw new KotobaseException('Unable to initialize cURL', 'transport_error', retryable: true);
        }
        $headerLines = [];
        foreach ($headers as $name => $value) {
            $headerLines[] = $name . ': ' . $value;
        }
        curl_setopt_array($handle, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => $headerLines,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT_MS => (int) round($timeout * 1000),
        ]);
        $response = curl_exec($handle);
        if (!is_string($response)) {
            $message = curl_error($handle);
            curl_close($handle);
            throw new KotobaseException($message, 'transport_error', retryable: true);
        }
        $status = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
        curl_close($handle);
        return [$status, $response];
    }
}
