// In-memory runtime diagnostics for the status page. Lives in the server
// process (the poller and the routes share it). Resets on redeploy, which is
// fine — it only answers "what is happening right now?".
const state = {
  startedAt: new Date().toISOString(),
  lastPollAt: null,        // last time the mailbox was polled
  lastPollOk: null,        // true/false/null (never)
  lastPollError: null,     // error message of the last failed poll
  lastPollNew: 0,          // new messages seen in the last poll
  lastAgentPullAt: null,   // last time the local agent asked for a job
};

function recordPoll({ ok, error = null, newMsgs = null }) {
  state.lastPollAt = new Date().toISOString();
  state.lastPollOk = ok;
  state.lastPollError = ok ? null : (error || 'error desconocido');
  if (typeof newMsgs === 'number') state.lastPollNew = newMsgs;
}

function recordAgentPull() {
  state.lastAgentPullAt = new Date().toISOString();
}

module.exports = { state, recordPoll, recordAgentPull };
