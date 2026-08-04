const { connectLambda } = require('@netlify/blobs');
const { getUsageCount } = require('./_util/stats');

const ALLOWED_ORIGIN = process.env.SITE_URL || 'https://oneciak.com';

exports.handler = async (event) => {
  const headers = { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': ALLOWED_ORIGIN, 'Vary': 'Origin' };
  if (event.httpMethod === 'OPTIONS') return { statusCode: 204, headers: { ...headers, 'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Allow-Headers': 'Content-Type' }, body: '' };
  if (event.httpMethod !== 'GET') return { statusCode: 405, headers, body: 'Not Allowed' };
  try {
    connectLambda(event);
    const count = await getUsageCount();
    return { statusCode: 200, headers, body: JSON.stringify({ count }) };
  } catch (err) {
    return { statusCode: 200, headers, body: JSON.stringify({ count: 0 }) };
  }
};
