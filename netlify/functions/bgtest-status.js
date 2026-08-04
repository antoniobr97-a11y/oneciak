const { connectLambda, getStore } = require('@netlify/blobs');

exports.handler = async (event) => {
  connectLambda(event);
  const store = getStore('bgtest');
  let record;
  try { record = await store.get('run', { type: 'json' }); } catch (e) { record = null; }
  return { statusCode: 200, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(record || { status: 'none' }) };
};
