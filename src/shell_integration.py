from pathlib import Path
from typing import Optional

class ShellIntegration:
    ZSH_INTEGRATION = r"""
# Git AI Commit Integration
_gcommit(){
  local c=$BUFFER
  if a=$(alias ${BUFFER%% *} 2>/dev/null);then
    c=${a#*=};c=${c//\'/};c="$c "
  fi
  if [[ $c =~ ^git\ commit.*(-m|--message)\  && $BUFFER =~ ^[^\"]*$ ]];then
    BUFFER="$BUFFER\"$(gcommit)\""
    CURSOR=${#BUFFER}
    if zle -l | grep -q autosuggest-disable; then
      zle autosuggest-disable
    fi
  else
    zle expand-or-complete
  fi
  if zle -l | grep -q autosuggest-enable; then
    zle autosuggest-enable
  fi
}
zle -N _gcommit
bindkey "^I" _gcommit
"""

    @classmethod
    def install(cls) -> Optional[str]:
        """Install shell integration."""
        zshrc_path = Path.home() / ".zshrc"

        try:
            # Check if integration is already installed
            if zshrc_path.exists():
                content = zshrc_path.read_text()
                if "_gcmc" in content:
                    # Update existing integration
                    updated_content = content.replace(
                        content[content.index("_gcmc"):content.index("compdef _gcmc git") + len("compdef _gcmc git")],
                        cls.ZSH_INTEGRATION.strip()
                    )
                    with open(zshrc_path, "w") as f:
                        f.write(updated_content)
                    return "Zsh auto suggestion integration updated successfully. Please restart your shell or run: source ~/.zshrc"

                else:
                    # Add integration to .zshrc
                    with open(zshrc_path, "a") as f:
                        f.write("\n" + cls.ZSH_INTEGRATION)
                    return "Zsh auto suggestion integration installed successfully. Please restart your shell or run: source ~/.zshrc"

            else:
                # Create .zshrc and add integration
                with open(zshrc_path, "w") as f:
                    f.write(cls.ZSH_INTEGRATION)
                return "Zsh auto suggestion integration installed successfully. Please restart your shell or run: source ~/.zshrc"

        except Exception as e:
            return f"Failed to install shell integration: {str(e)}"
