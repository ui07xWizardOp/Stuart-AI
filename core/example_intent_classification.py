"""
Example usage of enhanced intent classification

Demonstrates the IntentClassificationResult with confidence scores,
reasoning, and alternative intents.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_orchestrator import AgentOrchestrator, Intent


def demonstrate_intent_classification():
    """Demonstrate enhanced intent classification"""
    print("=" * 70)
    print("Enhanced Intent Classification Demo")
    print("=" * 70)
    
    orchestrator = AgentOrchestrator()
    
    # Example commands
    commands = [
        "Create a detailed sales report from Q4 data",
        "Create workflow to backup my documents every night at 2am",
        "Remember that I prefer Python over JavaScript for backend work",
        "Search for the latest documentation on FastAPI",
        "Run the daily-backup workflow",
        "What's the status of task-12345?",
        "Automate the data processing pipeline",
        "Generate a summary of recent customer feedback",
    ]
    
    print("\nClassifying various commands:\n")
    
    for command in commands:
        print(f"Command: '{command}'")
        print("-" * 70)
        
        result = orchestrator.classify_intent(command)
        
        print(f"  Primary Intent: {result.intent.value}")
        print(f"  Confidence: {result.confidence:.2%}")
        print(f"  Reasoning: {result.reasoning}")
        
        if result.alternatives:
            print(f"  Alternative Intents:")
            for alt_intent, alt_score in result.alternatives[:3]:
                print(f"    - {alt_intent.value}: {alt_score:.2%}")
        
        print()
    
    print("=" * 70)
    print("\nDemonstrating low confidence fallback:\n")
    
    # Ambiguous command that might trigger fallback
    ambiguous_command = "Do something with the files"
    print(f"Command: '{ambiguous_command}'")
    print("-" * 70)
    
    result = orchestrator.classify_intent(ambiguous_command)
    
    print(f"  Primary Intent: {result.intent.value}")
    print(f"  Confidence: {result.confidence:.2%}")
    print(f"  Reasoning: {result.reasoning}")
    
    if result.confidence < 0.5:
        print(f"  ⚠️  Low confidence - may need clarification from user")
    
    print()
    print("=" * 70)


def demonstrate_result_serialization():
    """Demonstrate converting results to dictionary"""
    print("\nResult Serialization Demo")
    print("=" * 70)
    
    orchestrator = AgentOrchestrator()
    
    command = "Search for machine learning tutorials"
    result = orchestrator.classify_intent(command)
    
    print(f"\nCommand: '{command}'")
    print("\nSerialized Result:")
    print(result.to_dict())
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    demonstrate_intent_classification()
    demonstrate_result_serialization()
