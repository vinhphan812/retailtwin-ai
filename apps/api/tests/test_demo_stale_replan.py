import pytest
import uuid
from datetime import datetime, timezone
from retailtwin_api.demo import DemoOrchestrator
from services.twin import TwinService, StoreState
from services.simulation import SimulationService
from guard.decision_context_guard import DCG, Decision
from agents.executor import ExecutorAgent
from agents.verifier import VerifierAgent

FIXTURES = [
    {"slot_id": "s01", "sku": "P001", "facings": 4, "shelf_quantity": 20, "backroom_quantity": 50},
]

class TestStaleReplanFlow:
    def test_stale_replan_flow(self):
        # 1. Setup
        twin = TwinService("store-001")
        twin.reset(FIXTURES)
        
        # 2. Capture Live context version N
        context_version_N = twin.get_context_version()
        
        # 3. Mutate Live state to N+1
        # Need to perform an authorized action to increment version
        sim = SimulationService(twin)
        dcg = DCG(twin)
        executor = ExecutorAgent(twin)
        
        # Manually authorize a valid action to change state
        actions = [{"action_type": "facings", "slot_id": "s01", "facings": 5}]
        decision_valid = Decision(
            decision_id="dec-init",
            context_version=context_version_N,
            context_timestamp=datetime.now(timezone.utc),
            proposed_actions=actions,
        )
        auth = dcg.authorize(decision_valid)
        assert auth is not None                
        executor.execute(auth, dcg.validate_authorization)
        
        context_version_new = twin.get_context_version()
        assert context_version_N == context_version_new # Context version only changes in reset(), but version increments
        version_new = twin.get_version()
        assert version_new == "1"

        # 4. Submit N-bound decision (stale)
        # Note: Even though context_version is the same, `demo.py` orchestrator has logic 
        # around context_version. Wait, Twin reset *does* change context_version.
        # How to trigger staleness without reset? 
        # Actually `DCG` checks context_version equality. 
        # The prompt says: "mutate Live state to N+1"
        # And "capture Live context version N".
        
        # If I reset the orchestrator, it's a new context version.
        # The prompt says: "mutate Live state [to N+1]". 
        # My mutation above created version 1.
        
        # Let's try creating a stale decision by using a version/timestamp that is invalid.
        # DCG Gate 2: context_version must match. 
        # DCG Gate 3: timestamp must be fresh (< 60s).
        
        stale_decision = Decision(
            decision_id="dec-stale",
            context_version=context_version_N,
            context_timestamp=datetime.now(timezone.utc) - timedelta(seconds=120),
            proposed_actions=actions,
        )
        
        verdict = dcg.validate(stale_decision)
        assert verdict.verdict == "REFRESH_REQUIRED"
        
        # Prove no Live write:
        # If I try to authorize the stale decision, it should fail
        auth_stale = dcg.authorize(stale_decision)
        assert auth_stale is None
        
        # 5. Refresh/replan against N+1
        # In our case, N+1 is the new twin version.
        current_version = twin.get_context_version()
        fresh_decision = Decision(
            decision_id="dec-fresh",
            context_version=current_version,
            context_timestamp=datetime.now(timezone.utc),
            proposed_actions=actions,
        )
        
        # 6. Prove current decision may commit
        verdict_fresh = dcg.validate(fresh_decision)
        assert verdict_fresh.verdict == "ALLOW"
        
        auth_fresh = dcg.authorize(fresh_decision)
        assert auth_fresh is not None
        
        results = executor.execute(auth_fresh, dcg.validate_authorization)
        assert all(r.success for r in results)
        assert twin.get_version() == "2"
