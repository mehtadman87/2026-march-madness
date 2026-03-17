"""Unit tests for Dockerfile and CloudFormation template existence and content.

Requirements: 7.1, 7.2, 7.4
"""

import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dockerfile_exists():
    """Dockerfile must exist at the repository root. Requirements: 7.1"""
    assert os.path.isfile(os.path.join(_REPO_ROOT, "Dockerfile"))


def test_dockerfile_uses_python_312():
    """Dockerfile must use python:3.12 base image. Requirements: 7.1"""
    with open(os.path.join(_REPO_ROOT, "Dockerfile")) as f:
        content = f.read()
    assert "FROM python:3.12" in content


def test_dockerfile_copies_src():
    """Dockerfile must copy the src/ directory. Requirements: 7.1"""
    with open(os.path.join(_REPO_ROOT, "Dockerfile")) as f:
        content = f.read()
    assert "COPY src/" in content


def test_dockerfile_installs_requirements():
    """Dockerfile must install from requirements.txt. Requirements: 7.1"""
    with open(os.path.join(_REPO_ROOT, "Dockerfile")) as f:
        content = f.read()
    assert "requirements.txt" in content


def test_dockerfile_no_hardcoded_api_keys():
    """Dockerfile must not contain hardcoded API key values. Requirements: 7.3"""
    with open(os.path.join(_REPO_ROOT, "Dockerfile")) as f:
        content = f.read()
    # ENV vars should be set to empty string, not real keys
    assert 'LINKUP_API_KEY=""' in content or "LINKUP_API_KEY=" in content
    assert 'CBBD_API_KEY=""' in content or "CBBD_API_KEY=" in content


def test_cfn_template_exists():
    """deploy/agentcore-stack.yaml must exist. Requirements: 7.2"""
    assert os.path.isfile(os.path.join(_REPO_ROOT, "deploy", "agentcore-stack.yaml"))


def test_cfn_template_contains_agentcore_runtime():
    """CloudFormation template must define AWS::BedrockAgentCore::Runtime. Requirements: 7.2"""
    with open(os.path.join(_REPO_ROOT, "deploy", "agentcore-stack.yaml")) as f:
        content = f.read()
    assert "AWS::BedrockAgentCore::Runtime" in content
    assert "MarchMadnessBracketPredictor" in content
    # Verify correct service principal per AWS docs
    assert "bedrock-agentcore.amazonaws.com" in content


def test_cfn_template_has_outputs():
    """CloudFormation template must have an Outputs section. Requirements: 7.2"""
    with open(os.path.join(_REPO_ROOT, "deploy", "agentcore-stack.yaml")) as f:
        content = f.read()
    assert "Outputs:" in content
    assert "RuntimeArn" in content


def test_bedrock_agentcore_yaml_removed():
    """.bedrock_agentcore.yaml must not exist in the repository root. Requirements: 7.4"""
    assert not os.path.isfile(os.path.join(_REPO_ROOT, ".bedrock_agentcore.yaml"))
