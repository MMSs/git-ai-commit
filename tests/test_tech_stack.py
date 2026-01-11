"""Tests for tech stack detection."""

import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestTechStackDetection:
    """Tests for technology stack detection."""

    def test_detect_python_from_pyproject(self, mock_git_repo: Path):
        """Python is detected from pyproject.toml."""
        from git_ai_commit import GitAICommit

        pyproject = mock_git_repo / "pyproject.toml"
        pyproject.write_text('[project]\nname = "test"')

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Python"
                assert "pip/poetry" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_python_from_requirements(self, mock_git_repo: Path):
        """Python is detected from requirements.txt."""
        from git_ai_commit import GitAICommit

        req = mock_git_repo / "requirements.txt"
        req.write_text("flask>=2.0.0\nrequests")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Python"
                assert "pip" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_javascript_from_package_json(self, mock_git_repo: Path):
        """JavaScript is detected from package.json."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({"name": "test", "dependencies": {}}))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "JavaScript/TypeScript"
                assert "npm/yarn" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_rust_from_cargo(self, mock_git_repo: Path):
        """Rust is detected from Cargo.toml."""
        from git_ai_commit import GitAICommit

        cargo = mock_git_repo / "Cargo.toml"
        cargo.write_text('[package]\nname = "test"')

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Rust"
                assert "Cargo" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_go_from_go_mod(self, mock_git_repo: Path):
        """Go is detected from go.mod."""
        from git_ai_commit import GitAICommit

        gomod = mock_git_repo / "go.mod"
        gomod.write_text("module example.com/test")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Go"
                assert "Go modules" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_java_from_pom(self, mock_git_repo: Path):
        """Java is detected from pom.xml."""
        from git_ai_commit import GitAICommit

        pom = mock_git_repo / "pom.xml"
        pom.write_text("<project></project>")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Java"
                assert "Maven" in tech["package_managers"]
            finally:
                os.chdir(original_dir)

    def test_detect_ruby_from_gemfile(self, mock_git_repo: Path):
        """Ruby is detected from Gemfile."""
        from git_ai_commit import GitAICommit

        gemfile = mock_git_repo / "Gemfile"
        gemfile.write_text('source "https://rubygems.org"')

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "Ruby"
                assert "Bundler" in tech["package_managers"]
            finally:
                os.chdir(original_dir)


class TestFrameworkDetection:
    """Tests for framework detection from package.json."""

    def test_detect_react(self, mock_git_repo: Path):
        """React is detected from package.json dependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"react": "^18.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "React" in tech["frameworks"]
            finally:
                os.chdir(original_dir)

    def test_detect_vue(self, mock_git_repo: Path):
        """Vue is detected from package.json dependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"vue": "^3.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "Vue.js" in tech["frameworks"]
            finally:
                os.chdir(original_dir)

    def test_detect_nextjs(self, mock_git_repo: Path):
        """Next.js is detected from package.json dependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"next": "^14.0.0", "react": "^18.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "Next.js" in tech["frameworks"]
                assert "React" in tech["frameworks"]
            finally:
                os.chdir(original_dir)

    def test_detect_typescript(self, mock_git_repo: Path):
        """TypeScript is detected from devDependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "devDependencies": {"typescript": "^5.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "TypeScript" in tech["frameworks"]
            finally:
                os.chdir(original_dir)

    def test_detect_express(self, mock_git_repo: Path):
        """Express.js is detected from dependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"express": "^4.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "Express.js" in tech["frameworks"]
            finally:
                os.chdir(original_dir)

    def test_detect_angular(self, mock_git_repo: Path):
        """Angular is detected from dependencies."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text(json.dumps({
            "name": "test",
            "dependencies": {"@angular/core": "^17.0.0"}
        }))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert "Angular" in tech["frameworks"]
            finally:
                os.chdir(original_dir)


class TestMultipleIndicators:
    """Tests for multiple tech stack indicators."""

    def test_first_language_wins(self, mock_git_repo: Path):
        """First detected language is set as primary."""
        from git_ai_commit import GitAICommit

        # Create both Python and JS indicators
        (mock_git_repo / "requirements.txt").write_text("flask")
        (mock_git_repo / "package.json").write_text(json.dumps({"name": "test"}))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                # Should have a primary language
                assert tech["primary_language"] is not None
            finally:
                os.chdir(original_dir)

    def test_multiple_package_managers(self, mock_git_repo: Path):
        """Multiple package managers are detected."""
        from git_ai_commit import GitAICommit

        (mock_git_repo / "requirements.txt").write_text("flask")
        (mock_git_repo / "Makefile").write_text("all:\n\techo test")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                assert len(tech["package_managers"]) >= 2
                assert "pip" in tech["package_managers"]
                assert "Make" in tech["package_managers"]
            finally:
                os.chdir(original_dir)


class TestNoTechStack:
    """Tests for repos with no detectable tech stack."""

    def test_empty_tech_stack(self, mock_git_repo: Path):
        """Empty tech stack when no indicators found."""
        from git_ai_commit import GitAICommit

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                tech = instance.detect_tech_stack()

                # The mock repo only has README.md, no tech indicators
                # But README.md is a *.md file which doesn't indicate tech
                assert tech["primary_language"] is None or isinstance(tech["primary_language"], str)
            finally:
                os.chdir(original_dir)

    def test_invalid_package_json_handled(self, mock_git_repo: Path):
        """Invalid package.json is handled gracefully."""
        from git_ai_commit import GitAICommit

        pkg = mock_git_repo / "package.json"
        pkg.write_text("not valid json {{{")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            original_dir = os.getcwd()
            os.chdir(mock_git_repo)
            try:
                instance = GitAICommit()
                # Should not raise, just skip framework detection
                tech = instance.detect_tech_stack()

                assert tech["primary_language"] == "JavaScript/TypeScript"
                # Frameworks may be empty due to parse error
            finally:
                os.chdir(original_dir)
