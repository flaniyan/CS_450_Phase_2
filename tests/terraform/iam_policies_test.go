package terraformtests

import (
	"encoding/json"
	"path/filepath"
	"strings"
	"testing"

	"github.com/gruntwork-io/terratest/modules/terraform"
	tfjson "github.com/hashicorp/terraform-json"
	"github.com/stretchr/testify/require"
)

func TestIAMPoliciesDoNotUseWildcards(t *testing.T) {
	t.Parallel()

	terraformDir := filepath.Clean("../../infra/envs/dev")
	options := &terraform.Options{
		TerraformDir: terraformDir,
		PlanFilePath: "terraform.tfplan",
		NoColor:      true,
		Vars: map[string]interface{}{
			"aws_region":        "us-east-1",
			"artifacts_bucket":  "pkg-artifacts",
		},
	}

	terraform.InitAndPlan(t, options)
	planOutput, err := terraform.RunTerraformCommandAndGetStdoutE(t, options, "show", "-json", options.PlanFilePath)
	require.NoError(t, err, "terraform show -json must succeed")

	var plan tfjson.Plan
	err = json.Unmarshal([]byte(planOutput), &plan)
	require.NoError(t, err, "terraform plan output must be valid JSON")
	require.NotNil(t, plan.PlannedValues, "plan must include planned values")
	require.NotNil(t, plan.PlannedValues.RootModule, "plan must include a root module")

	var resources []*tfjson.StateResource
	collectModuleResources(plan.PlannedValues.RootModule, &resources)

	for _, resource := range resources {
		if resource == nil || resource.Type != "aws_iam_policy" {
			continue
		}

		policyRaw, ok := resource.AttributeValues["policy"]
		if !ok || policyRaw == nil {
			continue
		}

		policyStr, ok := policyRaw.(string)
		if !ok || strings.TrimSpace(policyStr) == "" {
			continue
		}

		var policyDoc map[string]interface{}
		err := json.Unmarshal([]byte(policyStr), &policyDoc)
		require.NoErrorf(t, err, "IAM policy %s must contain valid JSON", resource.Address)

		assertNoWildcardStatements(t, resource.Address, policyDoc)
	}
}

func collectModuleResources(module *tfjson.StateModule, acc *[]*tfjson.StateResource) {
	if module == nil {
		return
	}

	*acc = append(*acc, module.Resources...)

	for _, child := range module.ChildModules {
		collectModuleResources(child, acc)
	}
}

func assertNoWildcardStatements(t *testing.T, address string, policy map[string]interface{}) {
	statements, ok := policy["Statement"]
	if !ok {
		return
	}

	switch s := statements.(type) {
	case map[string]interface{}:
		assertStatementNoWildcard(t, address, s)
	case []interface{}:
		for _, entry := range s {
			stmt, ok := entry.(map[string]interface{})
			if !ok {
				continue
			}
			assertStatementNoWildcard(t, address, stmt)
		}
	}
}

func assertStatementNoWildcard(t *testing.T, address string, statement map[string]interface{}) {
	checkField := func(field string) {
		value, exists := statement[field]
		if !exists {
			return
		}

		require.Falsef(
			t,
			hasWildcard(value),
			"IAM policy %s contains wildcard %s",
			address,
			field,
		)
	}

	checkField("Action")
	checkField("Resource")
}

func hasWildcard(value interface{}) bool {
	switch v := value.(type) {
	case string:
		return strings.TrimSpace(v) == "*"
	case []interface{}:
		for _, item := range v {
			if hasWildcard(item) {
				return true
			}
		}
	case map[string]interface{}:
		// Handle structured values such as {"Fn::Join": [...] } by checking nested elements.
		for _, item := range v {
			if hasWildcard(item) {
				return true
			}
		}
	}
	return false
}

