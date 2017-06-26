`METADATA` Parser
-----------------
- PEP 345 says that Classifiers and Requires-Python fields can have markers;
  assuming anyone's ever used this feature, support it
- Obsoletes-Dist, Provides-Dist, Provides-Extra, and Requires-External are
  technically structured, but the payoff from parsing them isn't worth the
  work.  Do it anyway.
- Support `Description-Content-Type` (same syntax as a regular `Content-Type`
  field)
- Convert markers to a `dict` representation (This will require `packaging` to
  first expose markers' structured information)
