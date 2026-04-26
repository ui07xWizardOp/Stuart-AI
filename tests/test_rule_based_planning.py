"""
Tests for Rule-Based Planning in HybridPlanner

Tests template matching, parameter extraction, template population,
and plan generation for common task patterns.
"""

import pytest
from hybrid_planner import (
    HybridPlanner,
    PlanningContext,
    TaskComplexity,
    PlanStatus
)


class TestRuleBasedPlanning:
    """Test suite for rule-based planning functionality"""
    
    @pytest.fixture
    def planner(self):
        """Create HybridPlanner instance for testing"""
        return HybridPlanner(
            enable_llm_planning=False,  # Disable LLM for rule-based tests
            enable_rule_based_planning=True
        )
    
    @pytest.fixture
    def context(self):
        """Create planning context for testing"""
        return PlanningContext(
            available_tools=[
                "file_manager",
                "browser_agent",
                "knowledge_manager",
                "memory_system",
                "llm",
                "data_processor",
                "system_executor",
                "system_monitor"
            ]
        )
    
    # Template Matching Tests
    
    def test_match_template_read_file(self, planner):
        """Test template matching for read file operation"""
        goal = "read file test.txt"
        match = planner._match_template(goal)
        
        assert match is not None
        template_name, template, confidence = match
        assert template_name == "read_file"
        assert confidence > 0.3
    
    def test_match_template_write_file(self, planner):
        """Test template matching for write file operation"""
        goal = "write to file output.txt"
        match = planner._match_template(goal)
        
        assert match is not None
        template_name, template, confidence = match
        assert template_name == "write_file"
        assert confidence > 0.3
    
    def test_match_template_list_directory(self, planner):
        """Test template matching for list directory operation"""
        goal = "list files in /home/user"
        match = planner._match_template(goal)
        
        assert match is not None
        template_name, template, confidence = match
        assert template_name == "list_directory"
        assert confidence > 0.3
    
    def test_match_template_web_search(self, planner):
        """Test template matching for web search operation"""
        goal = "search for python tutorials"
        match = planner._match_template(goal)
        
        assert match is not None
        template_name, template, confidence = match
        assert template_name == "web_search"
        assert confidence > 0.3
    
    def test_match_template_no_match(self, planner):
        """Test template matching with no matching template"""
        goal = "perform complex multi-step analysis with conditional logic"
        match = planner._match_template(goal)
        
        # Should not match any template due to complexity
        assert match is None
    
    def test_match_template_pattern_priority(self, planner):
        """Test that pattern matches score higher than keyword matches"""
        goal = "read and summarize document.pdf"
        match = planner._match_template(goal)
        
        assert match is not None
        template_name, template, confidence = match
        # Should match read_and_summarize due to pattern
        assert template_name == "read_and_summarize"
    
    # Parameter Extraction Tests
    
    def test_extract_parameters_file_path(self, planner):
        """Test parameter extraction for file path"""
        goal = "read file test.txt"
        template = planner.PLAN_TEMPLATES["read_file"]
        params = planner._extract_parameters(goal, template)
        
        assert "file_path" in params
        assert params["file_path"] == "test.txt"
    
    def test_extract_parameters_quoted_path(self, planner):
        """Test parameter extraction with quoted file path"""
        goal = 'read file "my document.txt"'
        template = planner.PLAN_TEMPLATES["read_file"]
        params = planner._extract_parameters(goal, template)
        
        assert "file_path" in params
        assert params["file_path"] == "my document.txt"
    
    def test_extract_parameters_url(self, planner):
        """Test parameter extraction for URL"""
        goal = "fetch url https://example.com/page"
        template = planner.PLAN_TEMPLATES["fetch_url"]
        params = planner._extract_parameters(goal, template)
        
        assert "url" in params
        assert params["url"] == "https://example.com/page"
    
    def test_extract_parameters_query(self, planner):
        """Test parameter extraction for search query"""
        goal = "search for machine learning tutorials"
        template = planner.PLAN_TEMPLATES["web_search"]
        params = planner._extract_parameters(goal, template)
        
        assert "query" in params
        assert "machine learning tutorials" in params["query"]
    
    def test_extract_parameters_multiple(self, planner):
        """Test parameter extraction with multiple parameters"""
        goal = "move file source.txt to destination.txt"
        template = planner.PLAN_TEMPLATES["move_file"]
        params = planner._extract_parameters(goal, template)
        
        assert "source_path" in params
        assert "destination_path" in params
        assert params["source_path"] == "source.txt"
        assert params["destination_path"] == "destination.txt"
    
    def test_extract_parameters_missing(self, planner):
        """Test parameter extraction with missing parameters"""
        goal = "write to file"  # Missing file_path and content
        template = planner.PLAN_TEMPLATES["write_file"]
        params = planner._extract_parameters(goal, template)
        
        # Should have placeholders for missing params
        assert "file_path" in params
        assert "content" in params
        assert params["file_path"].startswith("<")
        assert params["content"].startswith("<")
    
    # Template Population Tests
    
    def test_populate_template_simple(self, planner):
        """Test template population with simple parameters"""
        template = planner.PLAN_TEMPLATES["read_file"]
        parameters = {"file_path": "test.txt"}
        
        steps = planner._populate_template(template, parameters)
        
        assert len(steps) == 1
        assert steps[0]["tool"] == "file_manager"
        assert steps[0]["action"] == "read"
        assert steps[0]["param_value"] == "test.txt"
    
    def test_populate_template_multiple_steps(self, planner):
        """Test template population with multiple steps"""
        template = planner.PLAN_TEMPLATES["write_file"]
        parameters = {"file_path": "output.txt", "content": "Hello World"}
        
        steps = planner._populate_template(template, parameters)
        
        assert len(steps) == 2
        assert steps[0]["action"] == "validate_path"
        assert steps[1]["action"] == "write"
        assert steps[1]["param_value"] == "output.txt"
    
    def test_populate_template_missing_param(self, planner):
        """Test template population with missing parameter"""
        template = planner.PLAN_TEMPLATES["read_file"]
        parameters = {}  # No parameters provided
        
        steps = planner._populate_template(template, parameters)
        
        assert len(steps) == 1
        # Should have placeholder for missing param
        assert steps[0]["param_value"].startswith("<")
    
    # Plan Generation Tests
    
    def test_generate_rule_based_plan_read_file(self, planner, context):
        """Test rule-based plan generation for read file"""
        goal = "read file test.txt"
        complexity = planner.classify_task_complexity(goal)
        
        plan = planner._generate_rule_based_plan(goal, context, complexity)
        
        assert plan is not None
        assert plan.goal == goal
        assert plan.planning_approach == "rule_based"
        assert plan.status == PlanStatus.VALID
        assert len(plan.steps) == 1
        assert plan.metadata["template_name"] == "read_file"
        assert "file_path" in plan.metadata["parameters"]
    
    def test_generate_rule_based_plan_write_file(self, planner, context):
        """Test rule-based plan generation for write file"""
        goal = "write to file output.txt"
        complexity = planner.classify_task_complexity(goal)
        
        plan = planner._generate_rule_based_plan(goal, context, complexity)
        
        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.steps[0]["action"] == "validate_path"
        assert plan.steps[1]["action"] == "write"
    
    def test_generate_rule_based_plan_web_search(self, planner, context):
        """Test rule-based plan generation for web search"""
        goal = "search for python tutorials"
        complexity = planner.classify_task_complexity(goal)
        
        plan = planner._generate_rule_based_plan(goal, context, complexity)
        
        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.steps[0]["tool"] == "browser_agent"
        assert plan.steps[0]["action"] == "search"
        assert plan.steps[1]["action"] == "fetch"
    
    def test_generate_rule_based_plan_composite(self, planner, context):
        """Test rule-based plan generation for composite operation"""
        goal = "read and summarize document.pdf"
        complexity = planner.classify_task_complexity(goal)
        
        plan = planner._generate_rule_based_plan(goal, context, complexity)
        
        assert plan is not None
        assert len(plan.steps) == 2
        assert plan.steps[0]["tool"] == "file_manager"
        assert plan.steps[1]["tool"] == "llm"
        assert plan.metadata["template_name"] == "read_and_summarize"
    
    def test_generate_rule_based_plan_no_match(self, planner, context):
        """Test rule-based plan generation with no matching template"""
        goal = "perform complex analysis with multiple conditional branches"
        complexity = planner.classify_task_complexity(goal)
        
        plan = planner._generate_rule_based_plan(goal, context, complexity)
        
        # Should return None when no template matches
        assert plan is None
    
    # Integration Tests
    
    def test_create_plan_uses_rule_based(self, planner, context):
        """Test that create_plan uses rule-based planning for simple tasks"""
        goal = "list files in /home/user"
        
        plan = planner.create_plan(goal, context)
        
        assert plan is not None
        assert plan.planning_approach == "rule_based"
        assert plan.complexity == TaskComplexity.SIMPLE
        assert len(plan.steps) > 0
    
    def test_plan_metadata_includes_template_info(self, planner, context):
        """Test that plan metadata includes template information"""
        goal = "read file test.txt"
        
        plan = planner.create_plan(goal, context)
        
        assert "template_name" in plan.metadata
        assert "match_confidence" in plan.metadata
        assert "parameters" in plan.metadata
        assert plan.metadata["rule_based"] is True
    
    def test_plan_estimated_duration(self, planner, context):
        """Test that plan includes estimated duration"""
        goal = "write to file output.txt"
        
        plan = planner.create_plan(goal, context)
        
        assert plan.estimated_duration_seconds is not None
        assert plan.estimated_duration_seconds > 0
        # Should be roughly 5 seconds per step
        assert plan.estimated_duration_seconds == len(plan.steps) * 5
    
    # Edge Cases
    
    def test_template_matching_case_insensitive(self, planner):
        """Test that template matching is case insensitive"""
        goal_lower = "read file test.txt"
        goal_upper = "READ FILE TEST.TXT"
        goal_mixed = "Read File Test.txt"
        
        match_lower = planner._match_template(goal_lower)
        match_upper = planner._match_template(goal_upper)
        match_mixed = planner._match_template(goal_mixed)
        
        assert match_lower is not None
        assert match_upper is not None
        assert match_mixed is not None
        assert match_lower[0] == match_upper[0] == match_mixed[0]
    
    def test_parameter_extraction_with_special_chars(self, planner):
        """Test parameter extraction with special characters in path"""
        goal = "read file /home/user/my-file_v2.txt"
        template = planner.PLAN_TEMPLATES["read_file"]
        params = planner._extract_parameters(goal, template)
        
        assert "file_path" in params
        assert "my-file_v2.txt" in params["file_path"]
    
    def test_multiple_template_matches_selects_best(self, planner):
        """Test that best template is selected when multiple match"""
        goal = "search for information"
        match = planner._match_template(goal)
        
        # Should match one of the search templates
        assert match is not None
        template_name = match[0]
        assert "search" in template_name.lower()


class TestTemplateLibrary:
    """Test suite for template library completeness"""
    
    @pytest.fixture
    def planner(self):
        """Create HybridPlanner instance"""
        return HybridPlanner()
    
    def test_template_library_has_file_operations(self, planner):
        """Test that template library includes file operations"""
        file_ops = [
            "read_file", "write_file", "list_directory",
            "delete_file", "move_file", "copy_file"
        ]
        
        for op in file_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_template_library_has_web_operations(self, planner):
        """Test that template library includes web operations"""
        web_ops = ["web_search", "fetch_url", "extract_web_content"]
        
        for op in web_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_template_library_has_knowledge_operations(self, planner):
        """Test that template library includes knowledge operations"""
        knowledge_ops = [
            "knowledge_search", "retrieve_memory", "summarize_content"
        ]
        
        for op in knowledge_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_template_library_has_data_operations(self, planner):
        """Test that template library includes data operations"""
        data_ops = ["process_data", "analyze_data"]
        
        for op in data_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_template_library_has_system_operations(self, planner):
        """Test that template library includes system operations"""
        system_ops = ["execute_command", "check_status"]
        
        for op in system_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_template_library_has_composite_operations(self, planner):
        """Test that template library includes composite operations"""
        composite_ops = ["read_and_summarize", "search_and_save"]
        
        for op in composite_ops:
            assert op in planner.PLAN_TEMPLATES
    
    def test_all_templates_have_required_fields(self, planner):
        """Test that all templates have required fields"""
        required_fields = ["keywords", "patterns", "parameters", "steps"]
        
        for template_name, template in planner.PLAN_TEMPLATES.items():
            for field in required_fields:
                assert field in template, f"Template {template_name} missing {field}"
    
    def test_all_template_steps_have_required_fields(self, planner):
        """Test that all template steps have required fields"""
        required_step_fields = ["tool", "action", "description"]
        
        for template_name, template in planner.PLAN_TEMPLATES.items():
            steps = template.get("steps", [])
            for i, step in enumerate(steps):
                for field in required_step_fields:
                    assert field in step, \
                        f"Template {template_name} step {i} missing {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
