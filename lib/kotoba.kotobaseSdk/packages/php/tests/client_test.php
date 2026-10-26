<?php

declare(strict_types=1);

require_once __DIR__ . '/../src/KotobaseException.php';
require_once __DIR__ . '/../src/QueryResult.php';
require_once __DIR__ . '/../src/KotobaseClient.php';

use NetKotobase\KotobaseClient;

$captured = null;
$transport = function ($url, $headers, $body, $timeout) use (&$captured): array {
    $captured = compact('url', 'headers', 'body', 'timeout');
    $request = json_decode($body, true, flags: JSON_THROW_ON_ERROR);
    return [200, json_encode([
        'ok' => true,
        'language' => $request['language'],
        'data' => ['rows' => [['Ada']]],
        'meta' => ['requestId' => 'req-1', 'elapsedMs' => 2],
    ], JSON_THROW_ON_ERROR)];
};

$client = new KotobaseClient('https://example.test/', 'secret', $transport);
$result = $client->cypher('MATCH (n:users) RETURN n.name');
assert($captured['url'] === 'https://example.test/xrpc/ai.gftd.apps.kotobase.query.execute');
assert($captured['headers']['authorization'] === 'Bearer secret');
assert($result->data['rows'][0][0] === 'Ada');

$graphdb = $client->graphdb('SELECT ?s WHERE { ?s ?p ?o }', ['database' => 'default']);
assert($graphdb->language === 'graphdb');
assert(json_decode($captured['body'], true, flags: JSON_THROW_ON_ERROR)['language'] === 'graphdb');
echo "ok\n";
