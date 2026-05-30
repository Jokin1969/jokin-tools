// Minimal in-memory rate limiter (no external deps).
//
// Good enough for a single-instance hub: it throttles abusive bursts (login
// brute-force, expensive endpoints) per key (IP by default). It is NOT a
// distributed limiter — if the app is ever scaled to multiple instances, move
// this to a shared store. Requires `app.set('trust proxy', …)` so req.ip
// reflects the real client behind Railway's proxy.

function rateLimit({ windowMs = 15 * 60 * 1000, max = 10, message = 'Demasiados intentos, inténtalo más tarde.', keyGenerator } = {}) {
  const hits = new Map(); // key -> [timestamps]

  // Periodically drop empty/old buckets so the map doesn't grow unbounded.
  const sweep = setInterval(() => {
    const now = Date.now();
    for (const [key, times] of hits) {
      const fresh = times.filter(t => now - t < windowMs);
      if (fresh.length) hits.set(key, fresh);
      else hits.delete(key);
    }
  }, windowMs);
  sweep.unref?.();

  return function rateLimitMiddleware(req, res, next) {
    const key = keyGenerator ? keyGenerator(req) : (req.ip || req.connection?.remoteAddress || 'unknown');
    const now = Date.now();
    const times = (hits.get(key) || []).filter(t => now - t < windowMs);

    if (times.length >= max) {
      const retryAfterMs = windowMs - (now - times[0]);
      res.set('Retry-After', String(Math.ceil(retryAfterMs / 1000)));
      return res.status(429).json({ error: message });
    }

    times.push(now);
    hits.set(key, times);
    next();
  };
}

module.exports = { rateLimit };
