"""Spawn targets. No environment import occurs in the decision process."""


def engine_main(connection,configuration):
    from q4engine import simulator_worker
    simulator_worker(connection,configuration)


def policy_main(connection,options,journal_path,metadata):
    import sys,time,traceback
    from q4controller import Q4Controller
    from q3client import Client,JsonlJournal
    assert 'q4engine' not in sys.modules and 'engine' not in sys.modules
    journal=JsonlJournal(journal_path,metadata)
    def transport(path,body,timeout):
        connection.send(('action',path,body))
        if not connection.poll(max(5,timeout)):raise TimeoutError('local response timed out')
        return connection.recv()
    client=Client('local-robot',journal,transport=transport)
    error=None;start=time.perf_counter()
    try:
        Q4Controller(client,options).run()
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop',error=error,traceback=traceback.format_exc()))
    finally:
        journal.close()
    connection.send(('done',dict(error=error,wall_time=time.perf_counter()-start,
                                exited=client.ledger.exited,engine_imported=False)))
    connection.close()
