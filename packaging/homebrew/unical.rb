# Homebrew Formula for unical
# To distribute via a Homebrew tap (e.g., Bert0ns/homebrew-tap):
# 1. Create a GitHub repo named homebrew-tap (or Bert0ns/tap)
# 2. Place this file in Formula/unical.rb inside the tap repo
# 3. Update the version and sha256 checksums from the latest release
# 4. Users install with: brew install Bert0ns/tap/unical

class Unical < Formula
  desc "Sync a read-only university calendar into a color-coded Google Calendar"
  homepage "https://github.com/Bert0ns/uni-calendar-coloring"
  version "1.4.0"
  license "MIT"

  on_macos do
    if Hardware::CPU.arm?
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-arm64.tar.gz"
      sha256 "8d46f58b240f0df990b3c8fa834925fdb462c28c21dc8592a5cacf5bdf726bdc"
    else
      url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-macos-x86_64.tar.gz"
      sha256 "8d46f58b240f0df990b3c8fa834925fdb462c28c21dc8592a5cacf5bdf726bdc"
    end
  end

  on_linux do
    url "https://github.com/Bert0ns/uni-calendar-coloring/releases/download/v#{version}/unical-linux-x86_64.tar.gz"
    sha256 "dce7ef530222d7fc625f43efe3c8d2233b5ac1c30b2b7a483be900d3d9acd1a8"
  end

  def install
    bin.install "unical"
  end

  test do
    assert_match "Sync and color Google Calendar events", shell_output("#{bin}/unical --help")
  end
end
