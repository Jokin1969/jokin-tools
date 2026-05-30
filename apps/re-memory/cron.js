const cron = require('node-cron');
const { getMemoriesDueToday, markSent } = require('./db');
const { sendMemoryEmail } = require('./email');
const { createBackup, hasDbChangedSinceLastBackup } = require('./backup');

// ─── Daily email job: 06:50 Madrid time ──────────────────────────────────────

function startCron() {
  cron.schedule('50 6 * * *', async () => {
    console.log('[cron] Running daily Re-memory send job…');
    try {
      const memories = getMemoriesDueToday();
      console.log(`[cron] Found ${memories.length} memories due today`);

      for (const memory of memories) {
        try {
          // Each memory is emailed to its own owner.
          await sendMemoryEmail(memory, memory.owner_email);
          markSent(memory.id, memory.frequency);
          console.log(`[cron] ✓ Memory #${memory.id} sent to ${memory.owner_email} and updated`);
        } catch (err) {
          console.error(`[cron] ✗ Failed to send memory #${memory.id}:`, err.message);
        }
      }
    } catch (err) {
      console.error('[cron] Fatal error in send job:', err);
    }
  }, { timezone: 'Europe/Madrid' });

  console.log('[cron] Re-memory daily job scheduled (06:50 Europe/Madrid)');

  // ─── Automatic backup job ─────────────────────────────────────────────────
  // Interval controlled by BACKUP_INTERVAL_HOURS (default: 2)
  const intervalHours = Math.max(1, parseInt(process.env.BACKUP_INTERVAL_HOURS || '2', 10));
  const backupCronExpr = `0 */${intervalHours} * * *`;

  cron.schedule(backupCronExpr, async () => {
    if (!hasDbChangedSinceLastBackup()) {
      console.log('[backup-cron] No changes since last backup, skipping');
      return;
    }
    console.log('[backup-cron] Changes detected, creating automatic backup…');
    try {
      const result = await createBackup();
      console.log(`[backup-cron] ✓ Done: ${result.filename}`);
    } catch (err) {
      console.error('[backup-cron] ✗ Failed:', err.message);
    }
  }, { timezone: 'Europe/Madrid' });

  console.log(`[cron] Backup job scheduled (every ${intervalHours}h, only on changes)`);
}

module.exports = { startCron };
