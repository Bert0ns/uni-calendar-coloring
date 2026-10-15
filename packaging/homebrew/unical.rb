# Homebrew Formula for unical
# To distribute via a Homebrew tap (e.g., Bert0ns/homebrew-tap):
# 1. Create a GitHub repo named homebrew-tap (or Bert0ns/tap)
# 2. Place this file in Formula/unical.rb inside the tap repo
# 3. Update the version and sha256 checksums from the latest release
# 4. Users install with: brew install Bert0ns/tap/unical

class Unical < Formula
  desc "Sync a read-only university calendar into a color-coded Google Calendar"
  homepage "https://github.com/Bert0ns/uni-calendar-coloring"
  version "1.3.0"
  license "MIT"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-arm64.tar.gz"
      sha256 "c5780638932503c64c613f860a37d6ba5087bc21ad3b794fcd1903973a8c45b3"
    else
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-x86_64.tar.gz"
      sha256 "c5780638932503c64c613f860a37d6ba5087bc21ad3b794fcd1903973a8c45b3"
    end
  end

  on_linux do
    url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-linux-x86_64.tar.gz"
    sha256 "52467562686caf970c60ac6bb035fd0c5f370bc51fb74a8528f644922d9025c1"
  end

  def install
    bin.install "unical"
  end

  test do
    assert_match "Sync and color Google Calendar events", shell_output("#{bin}/unical --help")
  end
end
