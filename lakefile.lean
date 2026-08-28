import Lake
open Lake DSL

package setlah where

@[default_target]
lean_lib SetLah where

lean_exe setlahDoctor where
  root := `SetLahDoctor

lean_exe setlahExamples where
  root := `LeanExamples

lean_exe setlahTests where
  root := `LeanTests
