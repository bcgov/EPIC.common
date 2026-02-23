from submit_api.models.proponent import Proponent as SubmitProponentModel
from submit_api.enums.proponent_status import ProponentStatus
from epic_cron.services.approved_condition_service import ApprovedConditionService

class ProponentStatusUpdater:
    @classmethod
    def update(cls, session_maker, _=None):
        print("Running ProponentStatusUpdater...")
        cls._update_by_conditions(session_maker)
        
        # Add other status checks here in the future (e.g., financial checks)

    @classmethod
    def _update_by_conditions(cls, session_maker):
        try:
            with session_maker() as session:
                ids = ApprovedConditionService.sync_approved_conditions(session)
                
                if not ids:
                    return

                print(f"Updating {len(ids)} proponents to ELIGIBLE")
                # Optimization: Perform bulk update directly at DB level
                session.query(SubmitProponentModel).filter(
                    SubmitProponentModel.id.in_(ids)
                ).update(
                    {SubmitProponentModel.status: ProponentStatus.ELIGIBLE},
                    synchronize_session=False
                )
                session.commit()
        except Exception as e:
            print(f"Error updating based on conditions: {e}")
