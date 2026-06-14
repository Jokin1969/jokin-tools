// ─── Initial user seeding ─────────────────────────────────────────────────────
// Creates the team's accounts on boot if they don't already exist. Everyone
// starts with the password 12345678 and must_change = true, so the hub forces a
// password change on first login. Idempotent: existing emails are skipped, so a
// user who already changed their password is never touched.
const store = require('./store');

const DEFAULT_PASSWORD = '12345678';

// Apps decided with the owner: regular users get Batchwork for now; the admin
// sees everything. App access per user can be edited later in /auth/admin.
const USER_APPS = 'batchwork';

const USERS = [
  { email: 'castilla@joaquincastilla.com', name: 'Joaquín Castilla',  role: 'admin' },
  { email: 'herana@cicbiogune.es',         name: 'Hasier Eraña',      role: 'user' },
  { email: 'jmoreno@cicbiogune.es',        name: 'Jorge Moreno',      role: 'user' },
  { email: 'cdiaz@cicbiogune.es',          name: 'Carlos Díaz',       role: 'user' },
  { email: 'csampedro@cicbiogune.es',      name: 'Cristina Sampedro', role: 'user' },
  { email: 'jgalarza@cicbiogune.es',       name: 'Josu Galarza',      role: 'user' },
  { email: 'nanjo@cicbiogune.es',          name: 'Nuño Anjo',         role: 'user' },
  { email: 'ppineiro@cicbiogune.es',       name: 'Patricia Piñeiro',  role: 'user' },
  { email: 'efernandez@cicbiogune.es',     name: 'Eva Férnandez',     role: 'user' },
  { email: 'msanjuan@cicbiogune.es',       name: 'Maitena San Juan',  role: 'user' },
  { email: 'nisusi@cicbiogune.es',         name: 'Nerea Isusi',       role: 'user' },
];

function seedInitialUsers() {
  let created = 0;
  for (const u of USERS) {
    try {
      if (store.getUserByEmail(u.email)) continue; // never touch an existing account
      store.createUser({
        email: u.email,
        name: u.name,
        password: DEFAULT_PASSWORD,
        role: u.role,
        apps: u.role === 'admin' ? '*' : USER_APPS,
        mustChange: true,
      });
      created++;
      console.log(`[auth] Seeded user: ${u.email} (${u.role})`);
    } catch (e) {
      console.error(`[auth] seed user ${u.email} failed:`, e.message);
    }
  }
  if (created) console.log(`[auth] Seeded ${created} initial user(s) with forced password change.`);
  return created;
}

module.exports = { seedInitialUsers, USERS, DEFAULT_PASSWORD };
