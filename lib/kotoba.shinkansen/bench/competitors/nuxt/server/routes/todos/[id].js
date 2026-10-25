export default defineEventHandler((event) => sendHtml(event, fixture().todoHtml(getRouterParam(event, 'id'))));
