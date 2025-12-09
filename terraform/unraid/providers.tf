# Docker provider - connects to Unraid's Docker daemon via SSH
provider "docker" {
  host = "ssh://root@192.168.20.9:22"

  ssh_opts = ["-o", "StrictHostKeyChecking=no", "-o", "IdentityFile=/home/james/.ssh/id_ed25519_automation"]

  # Alternatively, if you expose Docker TCP (not recommended without TLS):
  # host = "tcp://192.168.20.9:2375"
}

