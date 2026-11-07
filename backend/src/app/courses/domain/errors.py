class CourseError(ValueError):
    pass


class CourseNotFound(LookupError):
    pass


class CourseConflict(Exception):
    pass


class ContentNotReady(CourseConflict):
    pass
