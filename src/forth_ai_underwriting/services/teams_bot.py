"""
Microsoft Teams Bot integration for the AI Underwriting System.
Handles formatting validation results and user interaction.
"""

from typing import Dict, Any, List
from loguru import logger

from forth_ai_underwriting.core.schemas import ValidationResult


class TeamsBot:
    """Handles Microsoft Teams bot interactions and message formatting."""
    
    def __init__(self):
        pass
    
    def format_validation_results(self, results: List[ValidationResult]) -> str:
        """
        Formats validation results into a human-readable string for Teams.
        """
        formatted_output = ["📊 **Underwriting Validation Results**\n"]
        
        passed_count = 0
        total_count = len(results)
        
        for result in results:
            status_icon = "✅" if result.result == "Pass" else "❌"
            formatted_output.append(
                f"{status_icon} **{result.title}** ---- {result.result} ---- {result.reason}"
            )
            if result.result == "Pass":
                passed_count += 1
        
        if total_count > 0:
            success_rate = (passed_count / total_count) * 100
            formatted_output.append(
                f"\n📈 **Summary**: Passed {passed_count}/{total_count} checks ({success_rate:.1f}% success rate)"
            )
        
        return "\n".join(formatted_output)
    
    async def send_message(self, conversation_id: str, message: str):
        """
        Sends a message to a Teams conversation.
        (Placeholder - actual implementation would use Microsoft Graph API or Bot Framework SDK)
        """
        logger.info(f"Sending message to Teams conversation {conversation_id}: {message}")
        # In a real scenario, this would involve calling the Microsoft Graph API
        # or using the Bot Framework SDK to send the message.
        pass

    async def send_feedback_request(self, conversation_id: str, contact_id: str):
        """
        Sends a feedback request to the user in Teams.
        """
        feedback_message = (
            f"Please provide feedback for contact **{contact_id}**:\n"
            f"Rate our validation (1-5 stars) and provide a brief description.\n"
            f"Example: `feedback contact_id:{contact_id} rating:5 description:Very accurate!`"
        )
        await self.send_message(conversation_id, feedback_message)


