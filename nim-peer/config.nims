# begin Nimble config (version 2)
when withDir(thisDir(), system.fileExists("nimble.paths")):
  include "nimble.paths"
--define:
  "chronicles_sinks=textblocks[dynamic]"
--define:
  "chronicles_log_level=DEBUG"
# end Nimble config
