# Homebrew Formula for unical
# To distribute via a Homebrew tap (e.g., Bert0ns/homebrew-tap):
# 1. Create a GitHub repo named homebrew-tap (or Bert0ns/tap)
# 2. Place this file in Formula/unical.rb inside the tap repo
# 3. Update the version and sha256 checksums from the latest release
# 4. Users install with: brew install Bert0ns/tap/unical

class Unical < Formula
  desc "Sync a read-only university calendar into a color-coded Google Calendar"
  homepage "https://github.com/Bert0ns/uni-calendar-coloring"
  version "1.2.0"
  license "MIT"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-arm64.tar.gz"
      sha256 "d8db07decb7a5cfa7225aa0398267826f07eb9434b07b85bc018bfdbd7ecc8ad"
    else
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-x86_64.tar.gz"
      sha256 "d8db07decb7a5cfa7225aa0398267826f07eb9434b07b85bc018bfdbd7ecc8ad"
    end
  end

  on_linux do
    url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-linux-x86_64.tar.gz"
    sha256 "e889cb69a6846804613c3f3f2f7b2c5f45580d1011d3374706dc9fb66d19dc6f"
  end

  def install
    bin.install "unical"
  end

  test do
    assert_match "Sync and color Google Calendar events", shell_output("#{bin}/unical --help")
  end
end
