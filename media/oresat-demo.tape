Output media/oresat-demo.gif
Set Shell zsh
Set Theme "Catppuccin Mocha"
Set Width 1280
Set Height 740
Set FontSize 16
Set Padding 18
Set Framerate 15
Env PS1 "$ "
Hide
Type 'export SIM="${SIM:-sim}" && cd "$(git rev-parse --show-toplevel)" && clear' Enter
Show
Type "./demo" Enter
Wait+Screen@120s /done: /
Sleep 6s
