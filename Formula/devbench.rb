# typed: false
# frozen_string_literal: true

# Devbench — Developer utilities CLI + ConfigForge config converter
# Homebrew formula for `brew tap apeters247/devbench && brew install devbench`
#
# To update this formula after a new release:
#   1. Publish to PyPI: python3 -m twine upload dist/*
#   2. Grab the new SHA256: curl -sL https://pypi.org/pypi/devbench/json | jq -r '.releases["VERSION"][].digests.sha256'
#   3. Update `url` and `sha256` below
#   4. Commit and push (brew auto-discovers updates from this file)

class Devbench < Formula
  desc "9 developer tools + ConfigForge: 11-format config converter with comment preservation"
  homepage "https://naxiai.com/tools/devbench/"
  url "https://github.com/apeters247/devbench/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # update after tagging release
  license "MIT"

  depends_on "python@3.12"

  def install
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install_and_link buildpath
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/devbench --version")
    system "#{bin}/devbench", "cf", "--help"
    # Quick round-trip smoke test
    (testpath/"test.yaml").write "key: value\n"
    output = shell_output("#{bin}/devbench cf --from yaml --to json #{testpath}/test.yaml")
    assert_match '"key"', output
    assert_match '"value"', output
  end
end
