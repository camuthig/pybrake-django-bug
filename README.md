# Summary
This is an example Django project showcasing a bug in Pybrake when performance stats tracking is enabled in which
errors thrown by the database are not reported to Airbrake. To reproduce:

* Run a project on Django
* Use the `AirbrakeMiddleware`
* Enable `performance_stats` on the Airbrake notifier in `settings.py`
* Cause a database error to be thrown in a view

There error will not be captured and sent to Airbrake.

# Reproduction

Two tests are built in this project to demonstrate this functionality. Each sends a request to the project that will
result in a SQL exception. The first configures the Airbrake client to NOT track performance stats, and the second
enables performance stats. In both cases, the expectation is that the notifier should not filter the exception out.

The first test passes, and the second test fails.

To run these tests

```bash
pip install poetry
poetry install
pytest
```

To the best of my knowledge, this impacts all versions of Pybrake >= 0.4.6 at least.

# Root Issue

The root issue appears to be that the `pybrake.notifier.pybrake_error_filter`, which is automatically applied to all
`Notifier` instances, looks for any `pybrake` module calls in the traceback, and if any are found, the error is filtered
and not sent to Airbrake.

When `performance_stats` are enabled on the Django integration, all database calls are wrapped by a Pybrake function
in order to record the span of the query from start to finish. If an exception occurs in the database during this call
that wrapper is included in the traceback. 

I do not believe this would happen in th Flask integration since that uses signals from SQL Alchemy to track that start
and end of queries, and therefore does not wrap the underlying database calls.

Below is an example stacktrace:

```
Traceback (most recent call last):
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
  File "/Users/camuthig/projects/camuthig/pybrake-django-bug/pybrake_django_bug/urls.py", line 26, in err
    cursor.execute("invalid SQL")
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/pybrake/django.py", line 174, in execute
    return self._record(self._cursor.execute, sql, params)
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/pybrake/django.py", line 185, in _record
    return method(sql, params)
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/backends/utils.py", line 67, in execute
    return self._execute_with_wrappers(
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/backends/utils.py", line 80, in _execute_with_wrappers
    return executor(sql, params, many, context)
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/backends/utils.py", line 84, in _execute
    with self.db.wrap_database_errors:
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/utils.py", line 91, in __exit__
    raise dj_exc_value.with_traceback(traceback) from exc_value
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/backends/utils.py", line 87, in _execute
    return self.cursor.execute(sql)
  File "<path>/envs/pybrake-django-bug/lib/python3.10/site-packages/django/db/backends/sqlite3/base.py", line 475, in execute
    return Database.Cursor.execute(self, query)
django.db.utils.OperationalError: near "invalid": syntax error
```