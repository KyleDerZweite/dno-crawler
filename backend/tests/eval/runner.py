#!/usr/bin/env python3
"""
NLP Evaluation Suite for Ollama Models.

Evaluates local Ollama models on three metrics:
1. Speed: Tokens per second
2. Fidelity: Percentage of outputs that are valid JSON matching the schema
3. Accuracy: Percentage of valid outputs with correct extracted data

Usage:
    python runner.py                    # Run with all available models
    python runner.py --model gemma3:1b  # Run with specific model
    python runner.py --verbose          # Show detailed output
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ollama

# Optional jsonschema import
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    print("⚠️  jsonschema not installed. Fidelity checks will use basic JSON validation only.")
    print("   Install with: pip install jsonschema>=4.20.0\n")


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class TestResult:
    """Result of a single test case for a single model."""
    model: str
    test_name: str
    input_text: str
    
    # Metrics
    tokens_per_second: float = 0.0
    is_valid_json: bool = False
    matches_schema: bool = False
    is_accurate: bool = False
    
    # Raw data
    raw_output: str = ""
    parsed_output: dict | None = None
    expected_output: dict | None = None
    error: str | None = None
    
    # Timing
    generation_time_ms: float = 0.0
    total_tokens: int = 0


@dataclass
class ModelMetrics:
    """Aggregated metrics for a single model."""
    model: str
    total_tests: int = 0
    
    # Speed
    avg_tokens_per_second: float = 0.0
    min_tokens_per_second: float = float('inf')
    max_tokens_per_second: float = 0.0
    
    # Fidelity
    valid_json_count: int = 0
    schema_match_count: int = 0
    fidelity_percentage: float = 0.0
    
    # Accuracy
    accurate_count: int = 0
    accuracy_percentage: float = 0.0
    
    # Response Time (seconds)
    avg_response_time_s: float = 0.0
    min_response_time_s: float = float('inf')
    max_response_time_s: float = 0.0
    
    # Raw results
    results: list[TestResult] = field(default_factory=list)


# =============================================================================
# Core Evaluator
# =============================================================================

class NLPEvaluator:
    """Main evaluator class for running NLP model benchmarks."""
    
    def __init__(self, config_path: Path | None = None, verbose: bool = False):
        self.verbose = verbose
        self.config_path = config_path or Path(__file__).parent / "config.json"
        self.config = self._load_config()
        self.available_models: list[str] = []
        
    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _discover_models(self) -> list[str]:
        """Discover all locally available Ollama models."""
        try:
            model_list = ollama.list()
            models = [m.model for m in model_list.models]
            return models
        except Exception as e:
            print(f"❌ Error discovering models: {e}")
            return []
    
    def _extract_json(self, text: str) -> tuple[dict | None, str | None]:
        """Extract JSON from model output, handling markdown code blocks."""
        # Try to find JSON in code blocks first
        code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block_match:
            text = code_block_match.group(1)
        
        # Try to find inline JSON
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
                return parsed, None
            except json.JSONDecodeError as e:
                return None, f"JSON parse error: {e}"
        
        return None, "No JSON found in output"
    
    def _validate_schema(self, data: dict, schema: dict) -> bool:
        """Validate data against JSON schema."""
        if not HAS_JSONSCHEMA:
            # Basic validation: check required keys exist
            required = schema.get("required", [])
            return all(key in data for key in required)
        
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True
        except jsonschema.ValidationError:
            return False
    
    def _check_accuracy(self, parsed: dict, expected: dict) -> bool:
        """Check if parsed output matches expected output."""
        if not parsed or not expected:
            return False
        
        # Check all expected keys match (case-insensitive string comparison for strings)
        for key, expected_value in expected.items():
            if key not in parsed:
                return False
            
            parsed_value = parsed[key]
            
            # Normalize string comparisons
            if isinstance(expected_value, str) and isinstance(parsed_value, str):
                # Case-insensitive, whitespace-normalized comparison
                if expected_value.lower().strip() != parsed_value.lower().strip():
                    return False
            elif isinstance(expected_value, (int, float)) and isinstance(parsed_value, (int, float)):
                # Numeric comparison with tolerance
                if abs(expected_value - parsed_value) > 0.01:
                    return False
            else:
                if expected_value != parsed_value:
                    return False
        
        return True
    
    def _run_single_test(
        self,
        model: str,
        test_case: dict,
        input_text: str,
        expected_output: dict,
    ) -> TestResult:
        """Run a single test case for a model."""
        result = TestResult(
            model=model,
            test_name=test_case["name"],
            input_text=input_text,
            expected_output=expected_output,
        )
        
        prompt = test_case["prompt_template"].format(input=input_text)
        
        try:
            start_time = time.perf_counter()
            
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={
                    "temperature": 0.1,  # Low temperature for consistent output
                    "num_predict": 256,  # Limit output length
                }
            )
            
            end_time = time.perf_counter()
            
            # Calculate metrics
            result.raw_output = response.get("response", "")
            result.generation_time_ms = (end_time - start_time) * 1000
            
            # Token counts from response
            eval_count = response.get("eval_count", 0)
            eval_duration = response.get("eval_duration", 0)
            
            if eval_duration > 0:
                # eval_duration is in nanoseconds
                result.tokens_per_second = eval_count / (eval_duration / 1e9)
            result.total_tokens = eval_count
            
            # Parse output
            parsed, error = self._extract_json(result.raw_output)
            result.parsed_output = parsed
            
            if parsed is not None:
                result.is_valid_json = True
                result.matches_schema = self._validate_schema(
                    parsed, test_case.get("expected_schema", {})
                )
                result.is_accurate = self._check_accuracy(parsed, expected_output)
            else:
                result.error = error
                
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def evaluate_model(self, model: str) -> ModelMetrics:
        """Evaluate a single model across all test cases."""
        metrics = ModelMetrics(model=model)
        test_cases = self.config.get("test_cases", [])
        iterations = self.config.get("settings", {}).get("iterations_per_test", 1)
        
        for test_case in test_cases:
            inputs = test_case.get("inputs", [])
            expected_outputs = test_case.get("expected_outputs", [])
            
            for idx, (input_text, expected) in enumerate(zip(inputs, expected_outputs)):
                for iteration in range(iterations):
                    if self.verbose:
                        print(f"  [{test_case['name']}] Input {idx+1}/{len(inputs)}, "
                              f"Iteration {iteration+1}/{iterations}")
                    
                    result = self._run_single_test(model, test_case, input_text, expected)
                    metrics.results.append(result)
                    metrics.total_tests += 1
                    
                    # Aggregate speed metrics
                    if result.tokens_per_second > 0:
                        metrics.max_tokens_per_second = max(
                            metrics.max_tokens_per_second, result.tokens_per_second
                        )
                        metrics.min_tokens_per_second = min(
                            metrics.min_tokens_per_second, result.tokens_per_second
                        )
                    
                    # Aggregate fidelity metrics
                    if result.is_valid_json:
                        metrics.valid_json_count += 1
                    if result.matches_schema:
                        metrics.schema_match_count += 1
                    
                    # Aggregate accuracy metrics
                    if result.is_accurate:
                        metrics.accurate_count += 1
                    
                    # Aggregate response time metrics
                    response_time_s = result.generation_time_ms / 1000
                    metrics.max_response_time_s = max(metrics.max_response_time_s, response_time_s)
                    metrics.min_response_time_s = min(metrics.min_response_time_s, response_time_s)
        
        # Calculate averages and percentages
        if metrics.total_tests > 0:
            speeds = [r.tokens_per_second for r in metrics.results if r.tokens_per_second > 0]
            if speeds:
                metrics.avg_tokens_per_second = sum(speeds) / len(speeds)
            
            times = [r.generation_time_ms / 1000 for r in metrics.results]
            if times:
                metrics.avg_response_time_s = sum(times) / len(times)
            
            metrics.fidelity_percentage = (metrics.schema_match_count / metrics.total_tests) * 100
            metrics.accuracy_percentage = (metrics.accurate_count / metrics.total_tests) * 100
        
        return metrics
    
    def run(self, models: list[str] | None = None) -> list[ModelMetrics]:
        """Run evaluation for specified models or all available models."""
        if models:
            self.available_models = models
        else:
            print("🔍 Discovering available Ollama models...")
            self.available_models = self._discover_models()
        
        if not self.available_models:
            print("❌ No models available. Please install models with: ollama pull <model>")
            return []
        
        print(f"✅ Found {len(self.available_models)} models: {', '.join(self.available_models)}\n")
        
        all_metrics: list[ModelMetrics] = []
        
        for i, model in enumerate(self.available_models, 1):
            print(f"📊 Evaluating [{i}/{len(self.available_models)}] {model}...")
            metrics = self.evaluate_model(model)
            all_metrics.append(metrics)
            
            # Print quick summary
            print(f"   Speed: {metrics.avg_tokens_per_second:.1f} tok/s | "
                  f"Time: {metrics.avg_response_time_s:.2f}s | "
                  f"Fidelity: {metrics.fidelity_percentage:.1f}% | "
                  f"Accuracy: {metrics.accuracy_percentage:.1f}%\n")
        
        return all_metrics
    
    def print_report(self, all_metrics: list[ModelMetrics]) -> None:
        """Print a formatted report of all results."""
        print("\n" + "=" * 95)
        print("                              NLP EVALUATION REPORT")
        print("=" * 95)
        
        # Sort by accuracy, then fidelity, then speed (prefer faster response time)
        sorted_metrics = sorted(
            all_metrics,
            key=lambda m: (m.accuracy_percentage, m.fidelity_percentage, -m.avg_response_time_s),
            reverse=True,
        )
        
        # Header
        print(f"\n{'Model':<25} {'Speed':>10} {'Resp Time':>12} {'Fidelity':>10} {'Accuracy':>10}")
        print(f"{'':25} {'(tok/s)':>10} {'(seconds)':>12} {'(%)':>10} {'(%)':>10}")
        print("-" * 80)
        
        for m in sorted_metrics:
            speed_str = f"{m.avg_tokens_per_second:.1f}" if m.avg_tokens_per_second > 0 else "N/A"
            time_str = f"{m.avg_response_time_s:.2f}s"
            # Flag slow responses (>5s)
            if m.avg_response_time_s > 5:
                time_str = f"⚠️ {m.avg_response_time_s:.2f}s"
            print(f"{m.model:<25} {speed_str:>10} {time_str:>12} {m.fidelity_percentage:>9.1f}% "
                  f"{m.accuracy_percentage:>9.1f}%")
        
        print("-" * 80)
        
        # Best performers
        if sorted_metrics:
            best = sorted_metrics[0]
            fastest = min(all_metrics, key=lambda m: m.avg_response_time_s if m.avg_response_time_s > 0 else float('inf'))
            
            print(f"\n🏆 Best Overall:      {best.model}")
            print(f"⚡ Fastest Response:  {fastest.model} ({fastest.avg_response_time_s:.2f}s avg)")
        
        print("\n" + "=" * 95)
    
    def export_results(self, all_metrics: list[ModelMetrics], output_path: Path) -> None:
        """Export results to JSON file."""
        results = []
        for m in all_metrics:
            results.append({
                "model": m.model,
                "total_tests": m.total_tests,
                "speed": {
                    "avg_tokens_per_second": m.avg_tokens_per_second,
                    "min_tokens_per_second": m.min_tokens_per_second if m.min_tokens_per_second != float('inf') else 0,
                    "max_tokens_per_second": m.max_tokens_per_second,
                },
                "fidelity": {
                    "valid_json_count": m.valid_json_count,
                    "schema_match_count": m.schema_match_count,
                    "percentage": m.fidelity_percentage,
                },
                "accuracy": {
                    "accurate_count": m.accurate_count,
                    "percentage": m.accuracy_percentage,
                },
            })
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"results": results, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2)
        
        print(f"📁 Results exported to: {output_path}")
    
    def export_detailed_results(self, all_metrics: list[ModelMetrics], output_path: Path) -> None:
        """Export detailed results to a markdown file for human review."""
        lines = [
            "# NLP Evaluation - Detailed Results",
            f"\n**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n**Models tested:** {len(all_metrics)}",
            "\n---\n",
        ]
        
        for m in all_metrics:
            lines.append(f"## 🤖 {m.model}")
            lines.append(f"\n| Metric | Value |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Speed | {m.avg_tokens_per_second:.1f} tok/s |")
            lines.append(f"| Fidelity | {m.fidelity_percentage:.1f}% |")
            lines.append(f"| Accuracy | {m.accuracy_percentage:.1f}% |")
            lines.append("")
            
            # Group results by test name
            results_by_test: dict[str, list[TestResult]] = {}
            for r in m.results:
                if r.test_name not in results_by_test:
                    results_by_test[r.test_name] = []
                results_by_test[r.test_name].append(r)
            
            for test_name, results in results_by_test.items():
                lines.append(f"\n### Test: `{test_name}`\n")
                
                for i, r in enumerate(results, 1):
                    status = "✅" if r.is_accurate else ("⚠️" if r.is_valid_json else "❌")
                    lines.append(f"#### {status} Sample {i}")
                    lines.append(f"\n**Input:**")
                    lines.append(f"```")
                    lines.append(r.input_text)
                    lines.append(f"```")
                    
                    lines.append(f"\n**Raw Output:**")
                    lines.append(f"```")
                    # Truncate very long outputs
                    raw = r.raw_output[:500] + "..." if len(r.raw_output) > 500 else r.raw_output
                    lines.append(raw)
                    lines.append(f"```")
                    
                    lines.append(f"\n**Parsed JSON:**")
                    if r.parsed_output:
                        lines.append(f"```json")
                        lines.append(json.dumps(r.parsed_output, indent=2, ensure_ascii=False))
                        lines.append(f"```")
                    else:
                        lines.append(f"`{r.error or 'Failed to parse'}`")
                    
                    lines.append(f"\n**Expected:**")
                    lines.append(f"```json")
                    lines.append(json.dumps(r.expected_output, indent=2, ensure_ascii=False))
                    lines.append(f"```")
                    
                    lines.append(f"\n| Valid JSON | Schema Match | Accurate | Speed |")
                    lines.append(f"|:----------:|:------------:|:--------:|:-----:|")
                    json_ok = "✅" if r.is_valid_json else "❌"
                    schema_ok = "✅" if r.matches_schema else "❌"
                    acc_ok = "✅" if r.is_accurate else "❌"
                    lines.append(f"| {json_ok} | {schema_ok} | {acc_ok} | {r.tokens_per_second:.1f} tok/s |")
                    lines.append("\n---\n")
            
            lines.append("\n---\n")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        print(f"📄 Detailed results exported to: {output_path}")


# =============================================================================
# CLI Entry Point
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NLP Evaluation Suite for Ollama Models")
    parser.add_argument("--model", "-m", type=str, help="Specific model to evaluate")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--export", "-e", type=str, help="Export results to JSON file")
    parser.add_argument("--detailed", "-d", type=str, help="Export detailed results to markdown file")
    parser.add_argument("--config", "-c", type=str, help="Path to config file")
    args = parser.parse_args()
    
    config_path = Path(args.config) if args.config else None
    evaluator = NLPEvaluator(config_path=config_path, verbose=args.verbose)
    
    models = [args.model] if args.model else None
    all_metrics = evaluator.run(models=models)
    
    if all_metrics:
        evaluator.print_report(all_metrics)
        
        if args.export:
            evaluator.export_results(all_metrics, Path(args.export))
        
        if args.detailed:
            evaluator.export_detailed_results(all_metrics, Path(args.detailed))
        
        # Auto-export if config setting is enabled
        if evaluator.config.get("settings", {}).get("export_detailed_results", False):
            default_path = Path(__file__).parent / "results_detailed.md"
            evaluator.export_detailed_results(all_metrics, default_path)


if __name__ == "__main__":
    main()