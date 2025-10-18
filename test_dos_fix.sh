#!/bin/bash

echo "🔥 DoS Fix Testing Script"
echo "========================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_passed=0
test_failed=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ $2${NC}"
        ((test_passed++))
    else
        echo -e "${RED}❌ $2${NC}"
        ((test_failed++))
    fi
}

echo -e "\n${YELLOW}1. Testing Python Driver Timeout Protection${NC}"
echo "Creating malicious validator that loops forever..."

# Test infinite loop timeout
cat > /tmp/malicious_test.py << 'EOF'
def validate(_):
    import time
    while True:
        time.sleep(0.1)  # Busy wait
EOF

VALIDATOR_TIMEOUT_SEC=2 VALIDATOR_MEMORY_MB=64 python3 -I -S src/validator/driver.py /tmp/malicious_test.py '{}' 2>/dev/null
exit_code=$?
test_result $([ $exit_code -ne 0 ] && echo 0 || echo 1) "Infinite loop timeout (exit code: $exit_code, should be non-zero)"

rm -f /tmp/malicious_test.py

echo -e "\n${YELLOW}2. Testing Memory Limit Protection${NC}"
cat > /tmp/memory_hog.py << 'EOF'
def validate(_):
    try:
        # Try to allocate a lot of memory
        x = "x" * (100 * 1024 * 1024)  # 100MB
        return {"allow": True, "reason": "allocation succeeded"}
    except MemoryError:
        return {"allow": False, "reason": "memory limit hit"}
EOF

VALIDATOR_TIMEOUT_SEC=5 VALIDATOR_MEMORY_MB=1 python3 -I -S src/validator/driver.py /tmp/memory_hog.py '{}' 2>/dev/null
exit_code=$?
test_result $([ $exit_code -eq 137 ] || [ $exit_code -eq 1 ]) "Memory limit protection (exit code: $exit_code)"

rm -f /tmp/memory_hog.py

echo -e "\n${YELLOW}3. Testing Happy Path${NC}"
cat > /tmp/good_validator.py << 'EOF'
def validate(data):
    return {"allow": True, "reason": "validation passed"}
EOF

python3 -I -S src/validator/driver.py /tmp/good_validator.py '{"test": true}' 2>/dev/null
exit_code=$?
test_result $([ $exit_code -eq 0 ]) "Happy path validation (exit code: $exit_code, should be 0)"

rm -f /tmp/good_validator.py

echo -e "\n${YELLOW}4. Testing Unit Tests${NC}"
if command -v python3 &> /dev/null && [ -f "requirements.txt" ]; then
    source .venv/bin/activate 2>/dev/null || true
    python3 -m pytest tests/unit/test_validator_timeout.py -q --tb=short >/dev/null 2>&1
    test_result $? "Unit tests execution"
else
    echo -e "${YELLOW}⚠️  Skipping unit tests (python3 or venv not available)${NC}"
fi

echo -e "\n${YELLOW}5. Testing Node.js Service Syntax${NC}"
if command -v node &> /dev/null; then
    node -c src/services/validator.js 2>/dev/null
    test_result $? "Node.js validator service syntax check"
else
    echo -e "${YELLOW}⚠️  Skipping Node.js syntax check (node not available)${NC}"
fi

echo -e "\n${YELLOW}6. Testing Environment Variables in Infrastructure${NC}"
if [ -f "infra/modules/ecs/main.tf" ]; then
    grep -q "VALIDATOR_TIMEOUT_SEC.*5" infra/modules/ecs/main.tf && \
    grep -q "VALIDATOR_MEMORY_MB.*128" infra/modules/ecs/main.tf && \
    grep -q "stopTimeout.*5" infra/modules/ecs/main.tf
    test_result $? "ECS environment variables and stopTimeout configured"
else
    echo -e "${YELLOW}⚠️  Skipping infrastructure check (Terraform files not found)${NC}"
fi

echo -e "\n${YELLOW}7. Testing CI Configuration${NC}"
if [ -f ".github/workflows/ci.yml" ]; then
    grep -q "test_validator_timeout.py" .github/workflows/ci.yml
    test_result $? "CI includes validator timeout tests"
else
    echo -e "${YELLOW}⚠️  Skipping CI check (workflows not found)${NC}"
fi

echo -e "\n${YELLOW}📊 Test Summary${NC}"
echo "=================="
echo -e "${GREEN}✅ Passed: $test_passed${NC}"
echo -e "${RED}❌ Failed: $test_failed${NC}"

if [ $test_failed -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All DoS protection tests PASSED! Your fix is working.${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some tests failed. Check the implementation.${NC}"
    exit 1
fi
