"""
Campaign Statistics Manager
Handles detailed campaign statistics and reporting
"""
from database import SessionLocal, Campaign, CallLog
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class CampaignStats:
    """Generate detailed campaign statistics"""
    
    @staticmethod
    def get_campaign_overview(campaign_id: int) -> Dict:
        """
        Get complete campaign overview with all statistics
        
        Returns:
            Dict with detailed stats
        """
        db = SessionLocal()
        try:
            campaign = db.query(Campaign).filter(
                Campaign.id == campaign_id
            ).first()
            
            if not campaign:
                return None
            
            return {
                'campaign_id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'total': campaign.total_numbers,
                'completed': campaign.completed_calls,
                'failed': campaign.failed_calls,
                'no_answer': campaign.no_answer_calls,
                'transferred': campaign.transferred_calls,
                'callbacks': campaign.callback_requests,
                'active': campaign.active_calls,
                'success_rate': round((campaign.completed_calls / campaign.total_numbers * 100), 1) if campaign.total_numbers > 0 else 0,
                'transfer_rate': round((campaign.transferred_calls / campaign.completed_calls * 100), 1) if campaign.completed_calls > 0 else 0,
                'callback_rate': round((campaign.callback_requests / campaign.completed_calls * 100), 1) if campaign.completed_calls > 0 else 0,
                'started_at': campaign.started_at,
                'completed_at': campaign.completed_at
            }
        finally:
            db.close()
    
    @staticmethod
    def get_transfer_requests(campaign_id: int) -> List[Dict]:
        """
        Get all numbers that pressed 1 (transfer)
        
        Returns:
            List of dicts with phone numbers and timestamps
        """
        db = SessionLocal()
        try:
            logs = db.query(CallLog).filter(
                CallLog.campaign_id == campaign_id,
                CallLog.action_taken == 'pressed_1'
            ).order_by(CallLog.timestamp.desc()).all()
            
            return [{
                'phone_number': log.phone_number,
                'timestamp': log.timestamp,
                'duration': log.duration,
                'status': log.status
            } for log in logs]
        finally:
            db.close()
    
    @staticmethod
    def get_callback_requests(campaign_id: int) -> List[Dict]:
        """
        Get all numbers that pressed 2 (callback)
        
        Returns:
            List of dicts with phone numbers and timestamps
        """
        db = SessionLocal()
        try:
            logs = db.query(CallLog).filter(
                CallLog.campaign_id == campaign_id,
                CallLog.action_taken == 'pressed_2'
            ).order_by(CallLog.timestamp.desc()).all()
            
            return [{
                'phone_number': log.phone_number,
                'timestamp': log.timestamp,
                'duration': log.duration,
                'status': log.status
            } for log in logs]
        finally:
            db.close()
    
    @staticmethod
    def get_failed_calls(campaign_id: int) -> List[Dict]:
        """Get all failed calls"""
        db = SessionLocal()
        try:
            logs = db.query(CallLog).filter(
                CallLog.campaign_id == campaign_id,
                CallLog.status == 'failed'
            ).order_by(CallLog.timestamp.desc()).all()
            
            return [{
                'phone_number': log.phone_number,
                'timestamp': log.timestamp,
                'notes': log.notes
            } for log in logs]
        finally:
            db.close()
    
    @staticmethod
    def get_no_answer_calls(campaign_id: int) -> List[Dict]:
        """Get all no-answer calls"""
        db = SessionLocal()
        try:
            logs = db.query(CallLog).filter(
                CallLog.campaign_id == campaign_id,
                CallLog.status == 'no-answer'
            ).order_by(CallLog.timestamp.desc()).all()
            
            return [{
                'phone_number': log.phone_number,
                'timestamp': log.timestamp
            } for log in logs]
        finally:
            db.close()
    
    @staticmethod
    def format_completion_summary(campaign_id: int) -> str:
        """
        Format campaign completion summary message
        
        Returns:
            Formatted message string for Telegram
        """
        overview = CampaignStats.get_campaign_overview(campaign_id)
        
        if not overview:
            return "Campaign not found"
        
        message = f"""
✅ **Campaign Completed: {overview['name']}**

📊 **Final Statistics:**
━━━━━━━━━━━━━━━━━━━━
• Total Numbers: {overview['total']}
• Completed: {overview['completed']} ({overview['success_rate']}%)
• Failed: {overview['failed']}
• No Answer: {overview['no_answer']}
• Transferred (Press 1): {overview['transferred']}
• Callbacks (Press 2): {overview['callbacks']}

📈 **Performance:**
• Transfer Rate: {overview['transfer_rate']}%
• Callback Rate: {overview['callback_rate']}%

⏱️ **Duration:**
Started: {overview['started_at'].strftime('%Y-%m-%d %H:%M:%S') if overview['started_at'] else 'N/A'}
Completed: {overview['completed_at'].strftime('%Y-%m-%d %H:%M:%S') if overview['completed_at'] else 'N/A'}
━━━━━━━━━━━━━━━━━━━━

Use buttons below to view detailed lists.
"""
        return message
    
    @staticmethod
    def format_transfer_list(campaign_id: int, limit: int = 50) -> str:
        """Format list of transfer requests"""
        transfers = CampaignStats.get_transfer_requests(campaign_id)[:limit]
        
        if not transfers:
            return "No transfer requests yet."
        
        message = f"🔔 **Transfer Requests** ({len(transfers)} total)\n\n"
        
        for i, transfer in enumerate(transfers, 1):
            time_str = transfer['timestamp'].strftime('%H:%M:%S')
            message += f"{i}. {transfer['phone_number']} - {time_str}\n"
        
        if len(transfers) >= limit:
            message += f"\n_Showing first {limit} results_"
        
        return message
    
    @staticmethod
    def format_callback_list(campaign_id: int, limit: int = 50) -> str:
        """Format list of callback requests"""
        callbacks = CampaignStats.get_callback_requests(campaign_id)[:limit]
        
        if not callbacks:
            return "No callback requests yet."
        
        message = f"📞 **Callback Requests** ({len(callbacks)} total)\n\n"
        
        for i, callback in enumerate(callbacks, 1):
            time_str = callback['timestamp'].strftime('%H:%M:%S')
            message += f"{i}. {callback['phone_number']} - {time_str}\n"
        
        if len(callbacks) >= limit:
            message += f"\n_Showing first {limit} results_"
        
        return message
    
    @staticmethod
    def export_campaign_data(campaign_id: int, export_type: str = 'all') -> str:
        """
        Export campaign data to CSV format
        
        Args:
            campaign_id: Campaign ID
            export_type: 'all', 'transfers', 'callbacks', 'failed', 'no_answer'
        
        Returns:
            CSV string
        """
        csv_lines = []
        
        if export_type == 'transfers':
            csv_lines.append("Phone Number,Timestamp,Duration,Status")
            transfers = CampaignStats.get_transfer_requests(campaign_id)
            for t in transfers:
                csv_lines.append(f"{t['phone_number']},{t['timestamp']},{t['duration']},{t['status']}")
        
        elif export_type == 'callbacks':
            csv_lines.append("Phone Number,Timestamp,Duration,Status")
            callbacks = CampaignStats.get_callback_requests(campaign_id)
            for c in callbacks:
                csv_lines.append(f"{c['phone_number']},{c['timestamp']},{c['duration']},{c['status']}")
        
        elif export_type == 'failed':
            csv_lines.append("Phone Number,Timestamp,Notes")
            failed = CampaignStats.get_failed_calls(campaign_id)
            for f in failed:
                csv_lines.append(f"{f['phone_number']},{f['timestamp']},{f['notes']}")
        
        elif export_type == 'no_answer':
            csv_lines.append("Phone Number,Timestamp")
            no_answer = CampaignStats.get_no_answer_calls(campaign_id)
            for n in no_answer:
                csv_lines.append(f"{n['phone_number']},{n['timestamp']}")
        
        else:  # all
            overview = CampaignStats.get_campaign_overview(campaign_id)
            csv_lines.append("Metric,Value")
            csv_lines.append(f"Campaign Name,{overview['name']}")
            csv_lines.append(f"Total Numbers,{overview['total']}")
            csv_lines.append(f"Completed,{overview['completed']}")
            csv_lines.append(f"Failed,{overview['failed']}")
            csv_lines.append(f"No Answer,{overview['no_answer']}")
            csv_lines.append(f"Transferred,{overview['transferred']}")
            csv_lines.append(f"Callbacks,{overview['callbacks']}")
            csv_lines.append(f"Success Rate,{overview['success_rate']}%")
        
        return "\n".join(csv_lines)
