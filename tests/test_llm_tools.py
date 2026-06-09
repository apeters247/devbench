import pytest
import subprocess
import json

# Helper to run CLI commands
def run_devbench_command(command, input_text=None):
    cmd = ["python3", "-m", "core.cli"] + command
    
    if input_text is not None:
        process = subprocess.run(cmd, input=input_text, capture_output=True, text=True)
    else:
        process = subprocess.run(cmd, capture_output=True, text=True)
    
    return process.stdout.strip(), process.stderr.strip(), process.returncode

def parse_json_output(output):
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return output

# --- Tests for devbench token ---

def test_token_basic_count():
    text = "Hello world, this is a test."
    stdout, stderr, returncode = run_devbench_command(["token"], input_text=text)
    assert returncode == 0
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "token"
    assert parsed_output["metadata"]["token_count"] > 0
    assert parsed_output["output"] == str(parsed_output["metadata"]["token_count"])
    assert "cl100k_base" in parsed_output["metadata"]["model"]

def test_token_different_model():
    text = "Hello world, this is a test."
    stdout, stderr, returncode = run_devbench_command(["token", "--model", "gpt2"], input_text=text)
    assert returncode == 0
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "token"
    assert parsed_output["metadata"]["token_count"] > 0
    assert parsed_output["metadata"]["model"] == "gpt2"

def test_token_empty_input():
    stdout, stderr, returncode = run_devbench_command(["token"], input_text="")
    assert returncode == 1 # Expect error
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "token"
    assert "Empty input" in parsed_output["error"]

def test_token_unknown_model():
    text = "some text"
    stdout, stderr, returncode = run_devbench_command(["token", "--model", "nonexistent_model"], input_text=text)
    # Falls back to estimation (no error) — graceful degradation
    assert returncode == 0
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "token"
    assert parsed_output["metadata"]["method"] == "estimate"

# --- Tests for devbench chunk ---

def test_chunk_basic_split():
    text = "This is the first sentence. This is the second sentence. This is the third sentence. This is the fourth sentence."
    # With default chunk_size=500, chunk_overlap=100, this should produce 1 chunk for this short text
    stdout, stderr, returncode = run_devbench_command(["chunk"], input_text=text)
    assert returncode == 0
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "chunk"
    assert parsed_output["metadata"]["chunk_count"] == 1
    chunks = json.loads(parsed_output["output"])
    assert len(chunks) == 1
    assert chunks[0].startswith("This is the first sentence.")

def test_chunk_multiple_chunks_and_overlap():
    long_text = " ".join([f"Sentence number {i}." for i in range(1, 100)]) # ~100 sentences
    stdout, stderr, returncode = run_devbench_command(["chunk", "--chunk-size", "50", "--chunk-overlap", "10"], input_text=long_text)
    assert returncode == 0
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "chunk"
    assert parsed_output["metadata"]["chunk_count"] > 1
    assert parsed_output["metadata"]["chunk_size"] == 50
    assert parsed_output["metadata"]["chunk_overlap"] == 10
    chunks = json.loads(parsed_output["output"])
    assert len(chunks) == parsed_output["metadata"]["chunk_count"]

    # More robust check for overlap: the last ~overlap sentences of chunk 0
    # should appear somewhere in chunk 1, or at least the chunks should share content
    if len(chunks) > 1:
        # Simple word-based overlap check: some words from the end of chunk 0
        # should appear at the beginning of chunk 1
        chunk0_words = set(chunks[0].split())
        chunk1_words = set(chunks[1].split())
        shared = chunk0_words & chunk1_words
        assert len(shared) > 0, f"No word overlap between chunks. Chunk 0 ends: ...{chunks[0][-100:]}, Chunk 1 starts: {chunks[1][:100]}..."
def test_chunk_empty_input():
    stdout, stderr, returncode = run_devbench_command(["chunk"], input_text="")
    assert returncode == 1 # Expect error
    parsed_output = parse_json_output(stdout)
    assert parsed_output["tool_name"] == "chunk"
    assert "Empty input" in parsed_output["error"]

def test_chunk_invalid_chunk_size():
    text = "some text"
    stdout, stderr, returncode = run_devbench_command(["chunk", "--chunk-size", "0"], input_text=text)
    assert returncode == 1
    parsed_output = parse_json_output(stdout)
    assert "Chunk size must be greater than 0" in parsed_output["error"]

def test_chunk_invalid_overlap():
    text = "some text"
    stdout, stderr, returncode = run_devbench_command(["chunk", "--chunk-overlap", "-50"], input_text=text)
    assert returncode == 1
    parsed_output = parse_json_output(stdout)
    assert "Chunk overlap cannot be negative" in parsed_output["error"]

def test_chunk_overlap_greater_than_size():
    text = "some text"
    stdout, stderr, returncode = run_devbench_command(["chunk", "--chunk-size", "10", "--chunk-overlap", "10"], input_text=text)
    assert returncode == 1
    parsed_output = parse_json_output(stdout)
    assert "Chunk overlap must be less than chunk size" in parsed_output["error"]
