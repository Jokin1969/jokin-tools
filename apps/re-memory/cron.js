const cron = require('node-cron');
const { getMemoriesDueToday, markSent } = require('./db');
const { sendMemoryEmail } = require('./email');

// ─── Daily cron: 06:50 Madrid time ───────────────────────────────────────────
// node-cron format: second(opt) minute hour day month weekday
// '50 6 * * *' with timezone Europe/Madrid

function startCron() {
  const task = cron.schedule('50 6 * * *', async () => {
    console.log('[cron] Running daily Re-memory send job…');
    try {
      const memories = getMemoriesDueToday();
      console.log(`[cron] Found ${memories.length} memories due today`);

      for (const memory of memories) {
        try {
          await sendMemoryEmail(memory);
          markSent(memory.id, memory.frequency);
          console.log(`[cron] ✓ Memory #${memory.id} sent and updated`);
        } catch (err) {
          console.error(`[cron] ✗ Failed to send memory #${memory.id}:`, err.message);
        }
      }
    } catch (err) {
      console.error('[cron] Fatal error in send job:', err);
    }
  }, {
    timezone: 'Europe/Madrid'
  });

  console.log('[cron] Re-memory daily job scheduled (06:50 Europe/Madrid)');
  return task;
}

module.exports = { startCron };
