const { connectLambda, getStore } = require('@netlify/blobs');

exports.handler = async (event) => {
  connectLambda(event);
  const store = getStore('bgtest');
  await store.setJSON('run', { status: 'started', startedAt: Date.now() });
  await new Promise((resolve) => setTimeout(resolve, 40000));
  await store.setJSON('run', { status: 'finished', finishedAt: Date.now() });
  return { statusCode: 200, body: 'done' };
};
