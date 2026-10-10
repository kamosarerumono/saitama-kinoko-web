# Public Word fixture

`simple.doc` is the Apache POI public test document from commit
`ae62bb5116b9aee19ebd5834e3a82066132c9f7f`:
https://github.com/apache/poi/blob/ae62bb5116b9aee19ebd5834e3a82066132c9f7f/test-data/document/simple.doc

SHA256: `4876e828e62d490fa188c7c4e47013e2e0dfdf02f5903dfd374bc0d2b2049ca1`.
Its text is “This is a simple file created with Word 97-SR2.”
The upstream LICENSE and NOTICE are included. This is not a user manuscript.

The real CLI integration test uses installed `antiword`, or the executable
specified by `ANTIWORD`. For a privately unpacked distribution, its normal
`ANTIWORDHOME` mapping directory may also be required. All other Word regression
tests use mocked converter output and do not require antiword. A skipped real
converter test is not evidence that conversion works on that host.
