"""Common isolation wrapper around an unchanged frozen Q4Controller import."""


def engine_main(connection,configuration):
    from q4engine import simulator_worker,Source
    configuration=dict(configuration)
    if configuration.get('sources') is not None:
        configuration['sources']=[Source(**s) if isinstance(s,dict) else s for s in configuration['sources']]
    simulator_worker(connection,configuration)


def policy_main(connection,options,journal_path,metadata):
    import sys,time,traceback,array
    sys.argv=['q4-feedback-policy']
    from q4controller import Q4Controller
    from q3client import Client,JsonlJournal
    from decision_guard import DecisionGuard
    assert 'q4engine' not in sys.modules and 'engine' not in sys.modules
    journal=JsonlJournal(journal_path,metadata)
    def transport(path,body,timeout):
        connection.send(('action',path,body))
        if not connection.poll(max(5,timeout)):raise TimeoutError('local response timed out')
        return connection.recv()
    client=Client('local-robot',journal,transport=transport);error=None;start=time.perf_counter()
    try:
        with DecisionGuard():Q4Controller(client,options).run()
    except Exception as exc:
        error=f'{type(exc).__name__}: {exc}'
        journal.append(dict(event='client_stop',error=error,traceback=traceback.format_exc()))
    finally:journal.close()
    connection.send(('done',dict(error=error,wall_time=time.perf_counter()-start,
                                exited=client.ledger.exited,engine_imported=False)))
    connection.close()
