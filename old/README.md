# MobiLLM

**Domain-specific LLM for cellular security**

MobiLLM is an intelligent multi-agent system designed specifically for 5G network security analysis and response. It leverages Large Language Models (LLMs) to provide automated threat detection, analysis, and mitigation strategies for cellular networks.

## 🚀 Features

- **Multi-Agent Architecture**: Specialized agents for different security tasks
- **5G Network Security**: Domain-specific knowledge for cellular security
- **MITRE ATT&CK Integration**: Maps threats to standard attack frameworks
- **Automated Response**: Suggests and executes countermeasures
- **Real-time Analysis**: Processes network events and telemetry data
- **Human-in-the-Loop**: Approval system for critical actions

## 🏗️ Architecture

MobiLLM uses a multi-agent architecture built with LangGraph:

<p align="center">
  <img src="mobillm_langgraph.png" alt="MobiLLM LangGraph Architecture" width="350"/>
</p>

### Agent Specializations

- **Chat Agent**: General network queries and service management
- **Security Analysis Agent**: Threat detection and analysis
- **Classification Agent**: MITRE ATT&CK technique mapping
- **Response Planning Agent**: Countermeasure strategy development
- **Config Tuning Agent**: Network configuration modifications

## 📋 Prerequisites

- Python 3.8+
- Google Gemini API key
- Docker (for xApp deployment)
- Kubernetes cluster (for production deployment)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/5GSEC/MobiLLM.git
cd MobiLLM
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables

```bash
export GOOGLE_API_KEY="your_gemini_api_key_here"
```

### 4. Verify Installation

```bash
python -c "from MobiLLM import MobiLLM_Multiagent; print('Installation successful!')"
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key | Required |
| `XAPP_ROOT_PATH` | xApp root directory | `./xApp` |
| `OAI_RAN_CU_CONFIG_PATH` | OAI RAN CU config path | Optional |

### Sample Data

The system includes sample 5G network data for testing:
- UE MobiFlow data
- Base Station MobiFlow data
- Security event data (MobieXpert, MobiWatch)
- Service status data

## 🚀 Quick Start

### Basic Usage

```python
from MobiLLM import MobiLLM_Multiagent

# Initialize the agent
agent = MobiLLM_Multiagent()

# Chat with the agent
response = agent.chat("How many UEs are connected to the network?")
print(response["output"])

# Security analysis
result = agent.security_analysis("Analyze event ID 123 for security threats")
print(result["output"])
```

### Security Analysis Example

```python
# Conduct security analysis
result = agent.invoke("""[security analysis] 
Event Details:
- Source: MobieXpert
- Name: RRC Null Cipher
- Cell ID: 20000
- UE ID: 54649
- Severity: Critical
- Description: UE uses null cipher mode in RRC session
""")

print("Threat Summary:", result["threat_summary"])
print("MITRE Techniques:", result["mitre_technique"])
print("Countermeasures:", result["countermeasures"])
```

## 🧪 Testing

### Run Test Suite

```bash
# Run all tests
python -m MobiLLM.test.test_llm

# Run baseline tests
python -m MobiLLM.test.baseline
```

### Test Individual Components

```bash
# Test LLM functionality
python -m MobiLLM.test_llm

# Test specific agents
python -c "
from MobiLLM import MobiLLM_Multiagent
agent = MobiLLM_Multiagent()
print('Agent initialized successfully')
"
```

