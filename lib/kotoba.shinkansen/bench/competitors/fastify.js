const fastify = require('fastify')();
const { home, homeEtag, todoHtml, liveHtml, port } = require('./common');
fastify.get('/', (req, reply) => {
  if (req.headers['if-none-match'] === homeEtag) return reply.code(304).header('etag', homeEtag).send();
  reply.header('cache-control', 'no-cache').header('etag', homeEtag).type('text/html; charset=utf-8').send(home);
});
fastify.get('/live', (req, reply) => {
  reply.header('cache-control', 'no-cache').type('text/html; charset=utf-8').send(liveHtml());
});
fastify.get('/todos/:id', (req, reply) => {
  reply.header('cache-control', 'no-cache').type('text/html; charset=utf-8').send(todoHtml(req.params.id));
});
fastify.listen({ port, host: '127.0.0.1' }).then(() => console.log('PORT\t' + fastify.server.address().port));
