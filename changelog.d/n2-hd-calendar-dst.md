### Fixed

- **The training calendar when the clocks go back:** a training session or match that ends around the end of daylight saving time no longer makes the calendar fail with *Failed to validate CalendarEvent*: the calendar shows it with its real length. In the hour that repeats, a session or match from the first pass of that hour no longer keeps Home Assistant busy; the attributes of the calendar stay empty until the clock reaches its end again.
