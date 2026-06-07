# typed: false
# frozen_string_literal: true

# Devbench — Developer utilities CLI + ConfigForge config converter
# Homebrew formula for `brew install devbench`
#
# Usage:
#   brew tap apeters247/devbench
#   brew install devbench
#
# Or with a custom formula URL:
#   brew install https://raw.githubusercontent.com/apeters247/devbench/master/Formula/devbench.rb

class Devbench < Formula
  desc "8 essential developer tools + ConfigForge config file conversion in your terminal"
  homepage "https://github.com/apeters247/devbench"
  url "https://github.com/apeters247/devbench/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000" # Placeholder — set during release
  license "MIT"
  revision 1

  depends_on "python@3.12"

  def install
    # Install the Python package into the prefix
    system "python3", "-m", "pip", "install", "--prefix=#{prefix}", "--no-deps", "."
    # Create a wrapper to ensure the right Python is used
    bin.install_symlink libexec/"bin/devbench" => "devbench"
  end

  test do
    system "#{bin}/devbench", "--version"
    system "#{bin}/devbench", "cf", "--help"
  end
end