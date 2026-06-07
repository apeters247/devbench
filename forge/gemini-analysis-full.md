The `configforge.py` script is a well-structured and comprehensive tool for configuration file conversion. It demonstrates good practices like modular functions, optional imports, and clear CLI integration. However, like any complex script, there are areas for improvement, potential bugs, missing edge cases, and feature requests.

Here's a detailed analysis:

---

### Bugs and Potential Issues

1.  **Line 361: `detect_format` - TOML Detection Fallback**:
    *   **Issue**: The code attempts `tomllib.loads(text)` as a fallback for TOML detection when top-level keys are present. This might be too broad. A simple string like `"key = \"value\""` could be valid in TOML but also in other formats or even just as text. The `re.search` before this is a good start, but relying solely on `tomllib.loads` without more context can lead to false positives if `tomllib` is forgiving.
    *   **Line Number**: 361
    *   **Test Case**:
        ```python
        # Input that might be mistaken for TOML by a too-lenient parser
        malicious_toml_like_string = """
        # This is just a comment
        key = "value"
        another_key = 123
        """
        # Assuming the actual content is meant to be plain text or similar
        # that doesn't conform to TOML structure, but tomllib might parse it.
        # We need to ensure detect_format correctly identifies it as 'unknown' or
        # a more appropriate format if applicable.
        ```

2.  **Line 449: `detect_format` - CSV `csv.Sniffer` with short inputs**:
    *   **Issue**: `csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")` and `csv.Sniffer().has_header(sample)` can raise `csv.Error` on very short or malformed inputs. The current `try-except` block catches these errors, but it might lead to an incorrect fallback to `csv.excel` or marking it as CSV when it's not. The logic for single-line CSV detection also seems a bit weak.
    *   **Line Number**: 449, 451, 452
    *   **Test Case**:
        ```python
        # Short, non-CSV text that might be misinterpreted
        short_non_csv = "just some text"
        # Single line that is not a CSV but contains commas
        single_line_with_commas_not_csv = "a, b, c"
        # Empty string
        empty_string = ""
        ```

3.  **Line 524: `_detect_timestamp` - Incomplete datetime parsing**:
    *   **Issue**: The regex `^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}` matches the start of a datetime but doesn't ensure the entire string is consumed. For example, `2024-01-15T10:30:00extra_stuff` would match. While `datetime.fromisoformat` would likely fail later, it's cleaner to validate the entire string with regex if possible. Also, it misses fractional seconds.
    *   **Line Number**: 524
    *   **Test Case**:
        ```python
        timestamp_with_extra = "2024-01-15T10:30:00extra_data"
        timestamp_with_fractional = "2024-01-15T10:30:00.123456" # This is valid ISO 8601
        timestamp_with_tz_and_fractional = "2024-01-15T10:30:00.123456+01:00" # This is valid ISO 8601
        ```

4.  **Line 557: `_infer_type` - Numeric parsing issues**:
    *   **Issue**: The strict numeric inference rejects underscore grouping (`1_000`) and leading zeros (`007`). While this is intentional for canonical representation, `007` is a valid octal integer in Python 2 but not a standard way to represent decimal integers in modern Python/JSON/YAML. However, YAML and TOML might allow octal literals. The current regex `[+-]?(?:0|[1-9]\d*)` correctly rejects leading zeros *unless* the number is exactly `0`. The check for `float` is also quite restrictive.
    *   **Line Number**: 557, 564
    *   **Test Case**:
        ```python
        # Valid octal string in some contexts, rejected here
        octal_string = "0o777" # This is actually Python's octal literal syntax. The regex would reject 0o777.
        decimal_with_leading_zeros = "007" # Rejected by regex.
        scientific_notation_large = "1e500" # Rejected by float regex due to math.isfinite check.
        ```
        *Correction*: The regex `[+-]?(?:0|[1-9]\d*)` correctly handles `0`. It would reject `007`. The `float` regex `[+-]?(?:(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+)` is also strict. It might be better to let `float()` try first, then check `isfinite`.

5.  **Line 615: `_coerce_dates` - Handling `Z` in ISO timestamps**:
    *   **Issue**: `fromisoformat` in Python versions prior to 3.11 does not directly support the trailing 'Z' for UTC. The code attempts to normalize this by replacing 'Z' with `+00:00`. However, this normalization might be problematic if the input string *actually* had both 'Z' and a timezone offset (which is invalid ISO 8601). A more robust approach would be to check for 'Z' and handle it explicitly.
    *   **Line Number**: 615
    *   **Test Case**:
        ```python
        iso_timestamp_z = "2024-01-15T10:30:00Z"
        # Potentially invalid input, but fromisoformat might have issues
        invalid_iso_tz = "2024-01-15T10:30:00+00:00Z"
        ```

6.  **Line 669: `parse_text` - XML `_xml_to_dict` empty root**:
    *   **Issue**: If an XML file has a root element with no children, text, or attributes (e.g., `<root></root>`), `_xml_to_dict` returns `{}`. This might be a valid representation, but it loses the root element name. The `_from_dict_to_xml` function later uses `root_name` and `item_name` which implies that the *structure* should be preserved.
    *   **Line Number**: 669
    *   **Test Case**:
        ```xml
        <empty_root></empty_root>
        ```

7.  **Line 707: `_xml_to_dict` - Flattening logic**:
    *   **Issue**: The `flatten` logic in `_xml_to_dict` seems to skip levels if a child has the same tag as its parent and is the *sole* child. This can lead to data loss or unexpected structure. For example, if you have `<items><item>A</item><item>B</item></items>`, and the parent also had a tag `item`, the flattening logic might incorrectly merge or drop items. The comment "Keep duplicate tags as list below" suggests it intends to handle this, but the current logic `pass # Keep duplicate tags as list below` within the `if flatten and tag in result...` block is a bit unclear. It's not clear how it actually keeps duplicates in this scenario if the `tag` is the same.
    *   **Line Number**: 707
    *   **Test Case**:
        ```xml
        <root>
          <item>
            <name>First Item</name>
          </item>
          <item>
            <name>Second Item</name>
          </item>
        </root>
        # If root itself was also an 'item' element, how would it flatten?
        # The current flattening is intended for the *parent's* structure.
        # Let's test a case where an intermediate node is skipped.
        <parent>
            <child>
                <grandchild>data</grandchild>
            </child>
        </parent>
        # If flatten_xml=True, this should ideally become "parent.child.grandchild": "data"
        # The current logic is meant to skip single-child intermediate nodes.
        # Test case for the 'pass' statement:
        <container>
            <element>
                <nested>value</nested>
            </element>
        </container>
        # If 'container' were to be skipped, and 'element' was the sole child.
        # The logic is: if flatten is true, and the tag is *already* in result,
        # AND the current result[tag] is a dict AND the *new* val is NOT a dict,
        # then we `pass`. This seems to be about handling sibling elements with the same tag.
        # The primary goal of flatten_xml is to reduce nesting depth.
        # The current implementation of flatten_xml in _flatten_dict is separate from _xml_to_dict's flatten.
        # This comment refers to _xml_to_dict's parameter. It's likely not used by _flatten_dict.
        ```
        *Correction*: The `flatten` parameter in `_xml_to_dict` is not directly passed to `_flatten_dict`. `_flatten_dict` is called later in `parse_text` if `flatten_xml` option is true. The `flatten` parameter inside `_xml_to_dict` seems to be an internal helper that isn't fully utilized or documented. The *actual* flattening happens in `_flatten_dict`.

8.  **Line 751: `_flatten_dict` - List handling**:
    *   **Issue**: The `_flatten_dict` function states "Lists and scalars are left in place under their dotted path." However, if a list contains dictionaries, `_flatten_dict` recursively calls itself on those dictionaries. This means list items that are dictionaries will have their keys flattened, but the list structure itself remains. This is usually the desired behavior, but it's worth noting. The potential issue is if the list itself contains nested lists, the recursion stops at the list level.
    *   **Line Number**: 751
    *   **Test Case**:
        ```python
        nested_list_of_dicts = {
            "list_data": [
                {"sub_key1": "value1", "sub_dict": {"nested_sub_key": "nested_value1"}},
                {"sub_key2": "value2", "another_list": [1, 2, 3]}
            ]
        }
        # Expected output: "list_data.0.sub_key1": "value1", "list_data.0.sub_dict.nested_sub_key": "nested_value1", ...
        # The 'another_list' will remain a list: "list_data.1.another_list": [1, 2, 3]
        ```

9.  **Line 841: `serialize` - TOML `null_handling="empty"`**:
    *   **Issue**: The `_to_toml` function handles `null_handling="empty"` by setting `key = ""`. This is a valid TOML string, but it's important to note that it's an empty string, not a "null" value. If the consumer expects a distinct null representation, this could be a point of confusion. TOML itself doesn't have a null type.
    *   **Line Number**: 841
    *   **Test Case**:
        ```python
        data_with_none = {"key": None}
        # serialize(data_with_none, "toml", null_handling="empty")
        # Expected output: "key = \"\""
        ```

10. **Line 905: `serialize` - INI `ConfigParser` `interpolation=None`**:
    *   **Issue**: `configparser.ConfigParser(interpolation=None)` disables interpolation. This is generally good for preventing unexpected substitutions, but it means that INI files with variables like `${VAR}` in their values will not have them resolved by `configparser`. If the user *expects* interpolation, this would be a bug. Given the purpose of config conversion, disabling it is usually safer.
    *   **Line Number**: 905
    *   **Test Case**:
        ```ini
        [section]
        var = hello
        interpolated = ${section::var}
        ```
        *   When this is parsed and then serialized back to INI without interpolation, `interpolated` might become an empty string or error depending on the `configparser`'s internal handling of unresolvable references when writing. The current code `cfg[section] = {str(k): str(v) for k, v in values.items()}` will write the value as is, so interpolation itself won't happen during serialization. The `read_string` part would have already failed or ignored it if interpolation was on. With `interpolation=None`, it should just parse as a literal string.

11. **Line 927: `serialize` - INI `ConfigParser` duplicate section names**:
    *   **Issue**: If the input dictionary for INI serialization has duplicate section names (e.g., `{"section": {...}, "section": {...}}`), Python dictionaries don't allow this. The last `section` definition would overwrite the first. However, the code `for section, values in data.items():` iterates over keys. If `data` is a standard dict, this is not an issue. If it's an ordered dict or some other structure that *could* allow duplicate keys conceptually, `configparser` might handle it in a specific way. Assuming standard dicts, this is not a bug. But it's good to be aware of the input assumptions.
    *   **Line Number**: 927
    *   **Test Case**: (This is more about input structure than a bug in code)
        ```python
        # This dictionary structure itself is invalid in Python
        # invalid_data = {
        #     "section": {"key1": "val1"},
        #     "section": {"key2": "val2"} # Duplicate key
        # }
        ```

12. **Line 945: `serialize` - INI nested lists/dicts**:
    *   **Issue**: The code explicitly checks `if isinstance(v, (dict, list)) and not isinstance(v, str): raise ValueError(...)` when serializing to INI. This is correct, as INI doesn't natively support nested structures. However, the error message is generic. It could be more specific about *which* key and section caused the problem.
    *   **Line Number**: 945
    *   **Test Case**:
        ```python
        nested_data = {
            "section": {
                "key1": "value1",
                "nested_list": [1, 2, 3] # This will raise an error
            }
        }
        ```

13. **Line 993: `serialize` - CSV `DictWriter` `extrasaction='ignore'`**:
    *   **Issue**: When serializing to CSV, `csv.DictWriter` is used with `extrasaction='ignore'`. This means if a row dictionary contains keys *not* present in the `fieldnames` list, they are silently dropped. While this is a common CSV behavior, it might be unexpected if the input data has heterogeneous dictionaries and the `fieldnames` are derived from only a subset. The logic for `fieldnames` collection seems to aim for comprehensiveness, but edge cases could exist.
    *   **Line Number**: 993
    *   **Test Case**:
        ```python
        data = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob", "age": 30} # 'age' is an extra field
        ]
        # If fieldnames were just ['id', 'name'], 'age' would be ignored.
        # The code attempts to collect all fieldnames, which mitigates this.
        ```

14. **Line 1038: `_from_dict_to_xml` - XML element naming**:
    *   **Issue**: The `_xml_name` function replaces invalid characters with `_`. While this is a reasonable approach, it doesn't guarantee uniqueness or prevent collisions if different invalid names map to the same valid name. For example, `My-Key` and `My_Key` both become `My_Key`. Also, it doesn't handle XML reserved characters like `xml` as a prefix for element names which might cause issues in some parsers or schemas.
    *   **Line Number**: 1038
    *   **Test Case**:
        ```python
        # Keys that might collide after sanitization
        invalid_keys = ["key-with-dash", "key_with_underscore", "key.dot"]
        # The function will convert all to "key_with_dash" or similar.
        # A real collision might happen if a user has "key-with-dash" and "key_with_dash" and expects them to be distinct in the output XML.
        ```

15. **Line 1138: `convert` - Comment preservation mismatch**:
    *   **Issue**: The `preserve_comments` logic extracts comments from YAML and INI. However, it does *not* extract comments from TOML, XML, JSON, CSV, or .env. If the input is one of these formats and has comments (e.g., in TOML, XML, or .env), they will be lost upon conversion.
    *   **Line Number**: 1138
    *   **Test Case**:
        ```python
        # TOML with comments
        toml_with_comments = """
        # This is a TOML comment
        key = "value" # inline comment
        [section]
        another_key = 123 ; another comment
        """
        # XML with comments
        xml_with_comments = """
        <!-- This is an XML comment -->
        <root>
          <element>value</element>
        </root>
        """
        # .env with comments
        env_with_comments = """
        # This is an env comment
        MY_VAR="hello" # inline env comment
        ANOTHER_VAR=123
        """
        ```

16. **Line 1157: `convert` - `_carry_comments` logic**:
    *   **Issue**: The `_carry_comments` logic is designed to pass comments between `convert` calls, primarily used by `round_trip`. The `comments = carry_comments if carry_comments is not None else []` line correctly initializes the `comments` list. However, after re-insertion, `comments = []` is set. This correctly consumes the comments for the current format. The `result["_comments"] = comments` line then adds any *remaining* comments (which should be none if re-insertion was successful) to the result dictionary. This seems correct.

17. **Line 1178: `convert_file` - Encoding and Error Handling**:
    *   **Issue**: `path.read_text(encoding="utf-8", errors="replace")` is used. While robust against invalid bytes, "replace" might silently corrupt data if the actual encoding is not UTF-8. A more user-friendly approach would be to try common encodings (UTF-8, Latin-1) or allow the user to specify encoding. Similarly, `Path(output_path).write_text(result["output"], encoding="utf-8")` assumes UTF-8 for output.
    *   **Line Number**: 1178, 1184
    *   **Test Case**:
        ```python
        # Input file with non-UTF-8 encoding (e.g., Latin-1)
        # Create a file named 'latin1_file.txt' with content like 'café' encoded in Latin-1
        # then try to convert it.
        ```

18. **Line 1239: `batch_convert` - `output_dir` mkdir**:
    *   **Issue**: `out_path.parent.mkdir(parents=True, exist_ok=True)` is called. This is correct for creating the output directory. However, if the `output_dir` itself does not exist, it will be created. If the script has permission issues creating it, the operation will fail. The error handling for `convert_file` is decent, but an issue here could lead to a misleading success message for `batch_convert` if `output_path` creation fails.
    *   **Line Number**: 1239
    *   **Test Case**:
        ```bash
        # Run batch_convert to a directory where the user has no write permissions
        # e.g., `/root/output` while running as a non-root user.
        ```

19. **Line 1274: `main` - Argument parsing for `from_fmt`**:
    *   **Issue**: The argument `-f` or `--from` is used for `from_fmt`. This is a common abbreviation for "from". However, in some contexts (like file paths), "from" can be a reserved word or imply specific behavior. It's generally safe as a CLI argument name, but `from_fmt` is clear.

20. **Line 1302: `main` - `to_fmt` detection for output file**:
    *   **Issue**: If `--output` is provided but `--to` is not, `to_fmt` is inferred from the output file extension. If the output file has no extension or an unknown extension (e.g., `output.myfile`), `to_fmt` defaults to `json` as per the subsequent `if not to_fmt: print("error: target format required...")`. This is reasonable, but the default `json` might be surprising if the user intended a different default.
    *   **Line Number**: 1302
    *   **Test Case**:
        ```bash
        # Create an output file without extension
        echo '{"a": 1}' > output_file
        configforge input.json --output output_file
        # This will try to convert to JSON.

        # Create an output file with unknown extension
        echo '{"a": 1}' > output.unknown
        configforge input.json --output output.unknown
        # This will try to convert to JSON.
        ```

21. **Line 1311: `main` - `args.input` missing for batch**:
    *   **Issue**: If `--batch` is used without specifying an input glob (`args.input` is `None`), the code correctly prints an error.
    *   **Line Number**: 1311
    *   **Test Case**:
        ```bash
        configforge --batch --to yaml --output-dir .
        # This should print an error.
        ```

22. **Line 1315: `main` - `args.to` missing for batch**:
    *   **Issue**: If `--batch` is used without specifying the target format (`args.to` is `None`), the code correctly prints an error.
    *   **Line Number**: 1315
    *   **Test Case**:
        ```bash
        configforge --batch input/*.json --output-dir .
        # This should print an error.
        ```

23. **Line 1328: `main` - Outputting to stdout with newline**:
    *   **Issue**: `sys.stdout.write(out if out.endswith("\n") else out + "\n")` ensures a newline. This is generally good practice for CLI tools writing to stdout, but it might interfere with piping or other tools expecting exact output without trailing newlines for certain formats (though this is rare for config files).
    *   **Line Number**: 1328

---

### Missing Edge Cases and Features

1.  **Feature: TOML - Inline Tables and Arrays**:
    *   **Missing**: While `_to_toml` handles basic inline structures, it doesn't seem to explicitly render nested dictionaries as TOML inline tables (`{ ... }`) or nested lists as inline arrays (`[ ... ]`) unless they are part of a table array. The `_toml_inline` function exists but is only used for array items in `_to_toml`.
    *   **Line Number**: `_to_toml` function (e.g., lines 887-891)
    *   **Test Code**:
        ```python
        inline_data = {
            "simple_inline_table": {"a": 1, "b": "hello"},
            "simple_inline_array": [1, "two", True],
            "nested_inline": {
                "inner_table": {"x": 10, "y": 20},
                "inner_array": [100, 200]
            }
        }
        # Expected TOML output (not currently produced):
        # simple_inline_table = { a = 1, b = "hello" }
        # simple_inline_array = [ 1, "two", true ]
        # nested_inline = { inner_table = { x = 10, y = 20 }, inner_array = [ 100, 200 ] }
        ```

2.  **Feature: TOML - Multiline Strings**:
    *   **Missing**: TOML supports multiline strings (`"""..."""` or `'''...'''`). The current `_toml_scalar` only handles basic escaping for single-line strings.
    *   **Line Number**: `_toml_scalar` (line 859)
    *   **Test Code**:
        ```python
        multiline_string_data = {
            "description": "This is a\nmulti-line\ndescription."
        }
        # Expected TOML output:
        # description = """
        # This is a
        # multi-line
        # description.
        # """
        ```

3.  **Feature: XML - Attributes vs. Elements**:
    *   **Missing**: The XML parsing (`_xml_to_dict`) and serialization (`_from_dict_to_xml`) have a convention where attributes are stored directly in the dictionary, and text content is under `"#text"`. This works well for many cases. However, it might not gracefully handle XML where an element could *both* have attributes and a child element with the same tag name (e.g., `<element attr="value"><element>text</element></element>`). The current logic might prioritize children. Also, there's no direct way to specify which XML properties should become attributes vs. child elements during serialization.
    *   **Line Number**: `_xml_to_dict` (lines 678-688), `_from_dict_to_xml` (lines 1008-1023)
    *   **Test Code**:
        ```xml
        <!-- XML that might challenge attribute/element mapping -->
        <data id="1">
            <value>100</value>
            <value type="int">200</value>
        </data>
        # The current parsing might map this to:
        # { "data": { "#text": null, "id": "1", "value": ["100", {"#text": "200", "type": "int"}] } }
        # This is reasonable, but the serialization needs to handle dicts that contain "#text" alongside attributes.
        # The issue is more about expressing intent during serialization: explicitly say 'attr="value"' or 'element="value"'.

        # Test for serialization: how to ensure 'id' is an attribute?
        data_to_xml_with_attr = {
            "data": {
                "id": {"_attr": "1"}, # Hypothetical way to signify attribute
                "value": 100,
                "value_with_type": {"_attr": {"type": "int"}, "_text": 200} # Hypothetical
            }
        }
        # Expected XML: <data id="1"><value>100</value><value type="int">200</value></data>
        ```

4.  **Feature: XML - CDATA Sections**:
    *   **Missing**: No explicit support for parsing or serializing XML CDATA sections (`<![CDATA[...]]>`).
    *   **Line Number**: Not present
    *   **Test Code**:
        ```xml
        <script><![CDATA[function alert(msg) { console.log(msg); }]]></script>
        ```

5.  **Feature: XML - XML Comments**:
    *   **Missing**: XML comments (`<!-- ... -->`) are not parsed or preserved. This is covered by the general comment preservation issue (Bug 15).
    *   **Line Number**: Not present in parsing, present in `convert` as unhandled.
    *   **Test Code**:
        ```xml
        <!-- This is an XML comment -->
        <data>
            <item>value</item>
        </data>
        ```

6.  **Feature: YAML - Anchors and Aliases**:
    *   **Missing**: YAML anchors (`&anchor`) and aliases (`*alias`) are not parsed or preserved. This allows defining a structure once and reusing it.
    *   **Line Number**: Not present
    *   **Test Code**:
        ```yaml
        defaults: &defaults
          adapter: postgresql
          encoding: unicode

        development:
          database: myapp_development
          <<: *defaults

        test:
          database: myapp_test
          <<: *defaults
        ```

7.  **Feature: YAML - Multi-document Handling Options**:
    *   **Missing**: The `parse_text` function has a `multi_doc` option (defaulting to `True`). However, the `serialize` function doesn't seem to have a direct way to *output* multi-document YAML from a list of dictionaries, unless `yaml.dump_all` is implicitly handled. `yaml.dump_all` is used, which is good. But there's no option to control its behavior like `indent`.
    *   **Line Number**: `parse_text` (line 638), `serialize` (line 793)
    *   **Test Code**:
        ```python
        # Serializing a list of dicts to multi-doc YAML
        multi_doc_data = [{"doc1": 1}, {"doc2": 2}]
        # The current serialize function will use dump_all.
        # The option to control `allow_unicode` and `indent` is present for `dump` and `dump_all`.
        # The usage of `default_flow_style=False, allow_unicode=True, sort_keys=sort_keys, indent=indent` for dump_all is correct.
        ```
        *Correction*: This feature *is* present for YAML serialization. The note about `indent` is addressed by the `options.get("indent", 2)`.

8.  **Feature: CSV - Type Inference and `infer_types` option**:
    *   **Missing**: The `parse_text` for CSV creates a list of dictionaries. All values are treated as strings by default. The `infer_types` option is available for INI but not for CSV. Adding type inference (int, float, bool, date) for CSV values would be beneficial.
    *   **Line Number**: `parse_text` CSV section (lines 703-729)
    *   **Test Code**:
        ```csv
        Name,Age,IsActive,Score
        Alice,30,true,95.5
        Bob,25,false,88
        Charlie,,"yes",77.7
        ```
        *   Expected parsed data with inference: `[{"Name": "Alice", "Age": 30, "IsActive": True, "Score": 95.5}, ...]`

9.  **Feature: CSV - Handling different delimiters and quoting**:
    *   **Missing**: While `csv.Sniffer` attempts to detect the dialect, explicit options to force delimiters (e.g., `--csv-delimiter=";"`) or quoting characters (`--csv-quotechar="'"`) would provide more control. The `csv.DictReader` can take `delimiter` and `quotechar` arguments.
    *   **Line Number**: `parse_text` CSV section (lines 703-729)
    *   **Test Code**:
        ```csv
        # CSV with semicolon delimiter and single quotes
        "Name";"Age"
        'Alice';30
        'Bob';25
        ```

10. **Feature: .env - Quoting and Escaping**:
    *   **Missing**: The `.env` parser (`parse_text`) strips surrounding quotes. This is generally fine. However, it doesn't explicitly handle complex escaping within quoted strings beyond removing the outer quotes. The `serialize` function (`_env_format_value`) handles newlines by quoting and escaping. This seems consistent. But it might not handle all edge cases of special characters or multi-line variable values as robustly as dedicated `.env` parsers.
    *   **Line Number**: `parse_text` `.env` section (lines 687-701)
    *   **Test Code**:
        ```env
        MY_VAR="value with \"quotes\" inside"
        ANOTHER_VAR='value with \'apostrophes\' inside'
        COMPLEX_VAR="value with \n newline and \r carriage return"
        # The current parser might strip quotes and then the inner quotes become part of the value.
        # For example, "value with \"quotes\" inside" might become "value with "quotes" inside" if the outer quotes are stripped directly.
        # The current stripping `v = v[1:-1]` is correct.
        ```

11. **Feature: Comment Preservation - Other Formats**:
    *   **Missing**: As noted in Bug 15, comments are not preserved for TOML, XML, JSON, CSV, and .env. Explicit support for these would be a significant feature. For XML and TOML, this is particularly desirable.
    *   **Line Number**: Not applicable, requires new parsing/serialization logic.
    *   **Test Code**: (See Bug 15 test cases)

12. **Feature: General Type Inference in CSV/JSON/TOML/XML**:
    *   **Missing**: While `_infer_type` exists for INI, it's not consistently applied to other formats like CSV or JSON parsing. JSON and TOML parsers handle their native types, but CSV values are all strings. If `infer_types` is `True`, `_infer_type` is used for INI parsing. It would be useful to extend this to other formats where it makes sense (e.g., inferring numbers, booleans, dates from CSV strings).
    *   **Line Number**: `parse_text` (various format sections)
    *   **Test Code**:
        ```json
        #
