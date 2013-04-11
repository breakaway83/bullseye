#!/usr/local/bin/python

import sys
import os
import shutil
import subprocess
import time
from datetime import datetime
import signal
import string
from threading import Timer

def build_under_bullseye(rundir, branch, covfile, full_path):
    os.environ['PATH'] = '/usr/bullseye/bin:/bin:/usr/local/bin:/usr/bin:/usr/kerberos/bin'
    #os.environ['COVFILE'] = os.path.join('/root', '.'.join([branch, 'cov']))
    os.environ['COVFILE'] = covfile
    print os.environ['COVFILE']
    os.chdir(rundir)
    if not os.path.exists(os.environ['SPLUNK_HOME']):
        os.mkdir(os.environ['SPLUNK_HOME'])
    subprocess.call(['/usr/bullseye/bin/cov01', '-1'])
    print os.environ
    time.sleep(60)
    subprocess.call(['./configure', '--disable-doxygen', 
                     '--without-unfinished-tests'], env=os.environ)
    if not os.path.exists(covfile):
        print 'covfile does not exist', covfile
        time.sleep(60)
    subprocess.call(['make', 'install'])
    if not os.path.exists(covfile):
        sys.exit('covfile does not exist')

    # Record time duration
    time1 = datetime.now()
    subprocess.call(['cmake/build_and_ctest.py', '-vO'])
    time2 = datetime.now()
    delta = time2 - time1
    f = open(os.path.join(full_path, 'time_spent.log'), 'a')
    f.write("Ctest time spent (seconds):\n")
    f.write("%s" % str(delta.seconds))
    f.write("\n")
    f.close()
    
    subprocess.call(['/usr/bullseye/bin/cov01', '-0']) 

def checkout(build_dir_snippet, p4_dir='/home/eserv/perforce/splunk',
             depot='//qa-centos-amd64-05/splunk'):
    rundir = os.path.join(p4_dir, build_dir_snippet)
    sync_target = '/'.join([depot, build_dir_snippet, '...'])
    print sync_target
    if os.path.exists(rundir):
        shutil.rmtree(rundir)
    if not os.path.exists(p4_dir):
        os.mkdir(p4_dir)
    os.chdir(p4_dir)
    x = subprocess.call(['/usr/local/bin/p4', '-u', 'bamboo', '-P', 'symantec', 'sync', '-f',
                         sync_target])
    print 'checked out'
    print x

def kill_proc(proc, timeout):
    timeout["value"] = True
    py_version = sys.version_info[:2]
    print "timeout, kill process."
    if py_version > (2,5):
        proc.kill()
    else:
        os.kill(proc.pid, signal.SIGTERM)

def run_qa_test(run_dir, test_dir, timeout_sec, args_list):
    # Setup PYTHONPATH
    py_path1 = os.path.join(run_dir, 'test')
    py_path2 = os.path.join(run_dir, 'test', 'lib')
    py_path3 = os.path.join(run_dir, 'test', 'lib', 'pytest', 'plugin')
    os.environ['PYTHONPATH'] = py_path1 + ':' + py_path2 + ':' + py_path3
    print os.environ['PYTHONPATH']
    # Setup SPLUNK_DB
    splunkdb_path = os.path.join(os.environ['SPLUNK_HOME'], 'var', 'lib', 'splunk')
    os.environ['SPLUNK_DB'] = splunkdb_path
    print os.environ['SPLUNK_DB']
    # Define splunk & py.test command path
    splunk_dir = os.path.join(os.environ['SPLUNK_HOME'], 'bin', 'splunk')
    pytest_cmd = os.path.join(os.environ['SPLUNK_HOME'], 'bin', 'py.test')
    print "py.test exists: %s" % os.path.exists(pytest_cmd)
    command_line = "%s %s %s %s %s" % (splunk_dir, 'cmd', 'python', pytest_cmd, args_list)
    command_list = [command_line, '-v']
    proc = subprocess.Popen(command_list, shell=True, cwd=test_dir,
                         bufsize=0, stdin=subprocess.PIPE,
                         stdout=None, stderr=None, close_fds=True)
    timeout = {"value" : False}
    #print proc.stdout.read()
    timer = Timer(timeout_sec, kill_proc, [proc, timeout])
    timer.start()
    stdout, stderr = proc.communicate()
    timer.cancel()
    return proc.returncode, stdout, stderr, timeout["value"]
    #x = p.wait()
    #print 'run search standard test'
    #print x
    #subprocess.call(['/usr/bullseye/bin/cov01', '-0']) 
    #return x

def build_contrib(rundir):
    #os.chdir(os.path.join(rundir, 'contrib'))
    full_rundir = os.path.join(rundir, 'contrib')
    print 'SPLUNK_HOME: '
    print os.environ['SPLUNK_HOME']
    print os.path.isdir(os.environ['SPLUNK_HOME'])
    #x = subprocess.call(['./buildit.py'])
    buildit = os.path.join(full_rundir, 'buildit.py') 
    print buildit
    subprocess.call(['/usr/bullseye/bin/cov01', '-0'])
    p = subprocess.Popen(buildit, shell=True, cwd=full_rundir,
                         bufsize=1024, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         close_fds=True)
    #while True:
    print p.stdout.read()
    x = p.wait()
    print 'built'
    print x
    return x

def generate_reports(covfile, branch_path, 
                     report_dir='/home/eserv/bullseye_reports', 
                     output_dir='/home/eserv/bullseye_reports'):
    #covfile = os.path.join(report_dir, 'bull.cov')
    html_file = os.path.join(branch_path, 'covbr.html')
    covbr_cmd = ' '.join(['/usr/bullseye/bin/covbr', '--file', covfile,
                          '--html'])
    p = subprocess.Popen(covbr_cmd, shell=True, bufsize=1024, 
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, close_fds=True)
    html = p.stdout.read()
    f = open(html_file, 'w')
    f.write(html)
    f.close() 
    report_commands = ['covdir', 'covsrc', 'covclass', 'covfn']
    for rc in report_commands:
        outfile = '.'.join([rc, 'csv']) 
        full_outfile = os.path.join(branch_path, outfile)
        full_rc = os.path.join('/usr/bullseye/bin', rc)
        full_cmd = ' '.join([full_rc, '--file', covfile, '-u', '-c'])
        p = subprocess.Popen(full_cmd, shell=True, bufsize=1024, 
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE, close_fds=True)
        (child_stdin, child_stdout, child_stderr) = (p.stdin, p.stdout, 
                                                     p.stderr)
        op = child_stdout.readlines()
        header_line = op[0]
        if rc == 'covfn':
            header_line = header_line.replace('out of', 'decision total')
            header_line = header_line.replace('%', 'decision_percent')
        else:
            header_line = header_line.replace('out of', 'total functions', 1)
            header_line = header_line.replace('%', 'func_percent', 1)
            header_line = header_line.replace('out of', 'decision total')
            header_line = header_line.replace('%', 'branch_percent')
        op[0] = header_line
        f = open(full_outfile, 'w')
        f.write(''.join(op))
        f.close()
        shutil.copy(covfile, branch_path)

def kill_proc_and_release_port():
    # This is a utility function to kill process bound on port
    # 8000 and 8089
    cmd = '/usr/sbin/lsof -i TCP:%s'
    ports = ['8000', '8089']
    for eachPort in ports:
        proc = subprocess.Popen([cmd % eachPort], shell=True, bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        if not stderr:
            if stdout:
                cmd_line = stdout.split('\n')
                if len(cmd_line) > 1:
                    second_line = cmd_line[1]
                    if second_line:
                        second_list = second_line.split()
                        if len(second_list) > 2:
                            pid = second_list[1]
                            if pid and isNumber(pid):
                                # Let us kill the process
                                print os.system('kill -9 ' + pid)

def isNumber(token):
    for char in token:
        if not char in string.digits: return False
    return True

def main(argv):
    os.environ['SPLUNK_HOME'] = '/home/eserv/splunk'
    os.environ['SPLUNK_DB'] = '/home/eserv/splunk/var/lib/splunk'
    os.environ['P4CLIENT'] = 'qa-centos-amd64-05'
    os.environ['PATH'] = os.environ['PATH'] + ':' + '/sbin'
    # To support multiple branch, default set to ace
    #branches_pool = {'bieber' : 'branches/bieber'}
    branches = {'current' : 'current'}
    #if len(argv) > 0:
    #    if argv[0][0:8] == "-branch=":
    #        if branches_pool.has_key(argv[0][8:]):
    #            branches = {argv[0][8:]: branches_pool[argv[0][8:]]}
    n = datetime.now()
    dirname = n.strftime('%Y-%m-%d-%H_%M')
    full_path = os.path.join('/home/eserv/bullseye_reports', dirname)
    if os.path.exists(full_path):
        shutil.rmtree(full_path)
    os.mkdir(full_path)
    for branch in branches:
        print branch
        branch_path = os.path.join(full_path, branch)
        os.mkdir(branch_path)
        dirname = branches[branch]
        covfile = '.'.join([branch, 'cov'])
        full_covfile = os.path.join('/home/eserv/bullseye_reports', covfile)
        if os.path.exists(full_covfile):
            os.remove(full_covfile)
        rundir = os.path.join('/home/eserv/perforce/splunk', dirname)
        print rundir

        # Kill hung process on port 8000 & 8089
        kill_proc_and_release_port()
        if os.path.exists(os.environ['SPLUNK_HOME']):
            shutil.rmtree(os.environ['SPLUNK_HOME'])
        os.mkdir(os.environ['SPLUNK_HOME'])
        checkout(dirname)
        x = build_contrib(rundir)
        if x:
            sys.exit('Could not build contrib')
        build_under_bullseye(rundir, branch, full_covfile, full_path)
        # After this, we need to archive Splunk build
        proc = subprocess.Popen(['/bin/tar', 'czf', '/home/eserv/splunk_archive/splunk.tar.gz', '/home/eserv/splunk'], bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        # Save splunk.version
        proc = subprocess.Popen(['%s %s' % (os.path.join(os.environ['SPLUNK_HOME'], 'bin', 'splunk'), 'version')], shell=True, bufsize=0, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
        stdout, stderr = proc.communicate()
        f = open(os.path.join(full_path, 'splunk.version.%s' % branch), 'w')
        f.write(stdout)
        f.close()

        # Need to update yaml file
        yaml_path = os.path.join(rundir, 'test', 'search', 'distributed')
        yaml_file = 'bamboo-self-all.yml'
        print "yaml_path=%s" % yaml_path
        updateYamlFile(yaml_path, yaml_file)

        #os.environ['COVFILE'] = covfile
        print "bullseye: %s" % os.environ['COVFILE']
        subprocess.call(['/usr/bullseye/bin/cov01', '-1'])
        tests = {
                 #'search standard' : os.path.join(rundir, 'test', 'search', 'standard'),
                 '3_cli' : os.path.join(rundir, 'test', 'tests', 'cli'),
                 '6_framework' : os.path.join(rundir, 'test', 'tests', 'framework'),
                 '4_rest' : os.path.join(rundir, 'test', 'tests', 'rest'),
                 '1_search longrunning' : os.path.join(rundir, 'test', 'search', 'longrunning'),
                 '2_search distributed' : os.path.join(rundir, 'test', 'search', 'distributed'),
                 '5_auth' : os.path.join(rundir, 'test', 'tests', 'auth')
                }
        args = {
                #'search standard' : '',
                '3_cli' : 'test_app.py test_find.py test_monitor.py test_password.py test_user.py test_tcp.py test_udp.py test_sync_async_search.py test_spool.py test_settings.py test_savedsearch.py test_forwarding.py test_index.py test_oneshot.py test_scripted.py test_receiving.py test_license.py test_deploy.py',
                '6_framework' : 'test_input_modular.py test_app_lwf.py test_app_scoped_inputs.py test_cli_diag.py test_cluster.py test_deployment_server.py test_forwarding_clone.py test_forwarding_persistent_q.py test_forwarding_single.py test_free_restrictions.py test_gdb_rolling.py test_host_regex.py test_input_admon_grp.py test_input_admon.py test_input_archive.py test_input_batch.py test_input_blacklist.py test_input_catastrophe.py test_input_compressed.py test_input_datetime.py test_input_during_restart.py test_input_exec.py test_input_fifo.py test_input_hostname_normalization.py test_input_i18n.py test_input_net.py test_input_networktail.py test_input_pathlen.py test_input_perfmon.py test_input_regmon.py test_input_remote_file_system.py test_input_rolling.py test_input_rotated.py test_input_script.py test_input_sinkhole.py test_input_source.py test_input_sourcetype.py test_input_tail_err_retry.py test_input_tailfeatures.py test_input_tcp.py test_input_uncompressed.py test_input_upload.py test_input_whitelist.py test_memory_consumption.py test_startup_warnings.py',
                #'cli' : 'test_tcp.py',
                #'rest' : '-k -windows test_saved_search.py'
                '4_rest' : '-k -windows test_saved_search.py test_scheduled_views.py test_search_distributed_config.py test_search_distributed_peers.py test_search_fields.py test_search_jobs_export.py test_search_parser.py test_search_results.py test_search_tags.py test_search_timeparser.py test_search_typeahead.py test_server_control.py test_server_info.py test_server_logger.py test_server_settings.py test_storage_passwords.py test_LDAP_authentication.py test_alerts_fired_alerts.py test_appbuilder.py test_apps_local.py test_auth_login.py test_authentication_changepassword.py test_authentication_httpauth-tokens.py test_authentication_users.py test_authorization_capabilities.py test_authorization_roles.py test_configs_conf.py test_data_indexes.py test_data_indexes_bucketInfo.py test_data_inputs_monitor.py test_data_inputs_oneshot.py test_data_inputs_script.py test_data_inputs_tcp_cooked.py test_data_inputs_tcp_raw.py test_data_inputs_tcp_ssl.py test_data_inputs_udp.py test_data_outputs_tcp_default.py test_data_outputs_tcp_group.py test_data_outputs_tcp_server.py test_data_outputs_tcp_syslog.py test_deployment_client.py test_deployment_server.py test_deployment_serverclass.py test_deployment_tenants.py test_directory.py test_fromxml.py test_ipv6_compliant.py test_licenser_groups.py test_licenser_licenses.py test_licenser_messages.py test_licenser_pools.py test_licenser_slaves.py test_licenser_stacks.py test_messages.py test_moving.py test_properties.py test_receivers_simple.py test_receivers_stream.py',
                '1_search longrunning' : '',
                '2_search distributed' : '-v --debug --dist-setup=bamboo-self-all-eserv.yml',
                '5_auth' : '--auth=auth.yml  -s'
                }
        # Sort the tests' keys
        tests_keys = tests.keys()
        tests_keys.sort()
        for aTest in tests_keys:
            print "Start %s test:" % aTest
            # At the end of each test
            # we do a cleanup
            splunk_bin = os.path.join(os.environ['SPLUNK_HOME'], 'bin', 'splunk')
            print "splunk_bin: %s" % splunk_bin
            subprocess.call([splunk_bin, 'stop'])
            subprocess.call([splunk_bin, 'clean', 'all', '-f'])
            subprocess.call([splunk_bin, 'start'])

            # Record the time spent
            time1 = datetime.now()
            rc, stdout, stderr, timeout_value = run_qa_test(rundir, tests[aTest], 39600, args[aTest])
            time2 = datetime.now()
            delta = time2 - time1
            f = open(os.path.join(full_path, 'time_spent.log'), 'a')
            f.write("%s  time spent (seconds):\n" % aTest)
            f.write("%s\n" % str(delta.seconds))
            f.close()

            if rc != 0:
                print '%s tests return code is %s, %s %s %s' % (aTest, rc, stdout, stderr, timeout_value)
            print 'finish %s test' % aTest
        # Run new_test - forwarder mgmt
        command = ['bash', '-c', 'source %s/bin/setSplunkEnv' % os.environ['SPLUNK_HOME']]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        proc.communicate()
        os.chdir('/home/eserv/perforce/splunk/current/new_test')
        command = ['bash', '-c', 'source /home/eserv/perforce/splunk/current/new_test/setTestEnv']
        proc = subprocess.Popen(command, stdout=subprocess.PIPE)
        proc.communicate()
        os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ":" + "/home/eserv/perforce/splunk/current/new_test/lib/splunktest/rest/feedparser"
        test_dir = '/home/eserv/perforce/splunk/current/new_test/tests/forwarder_mgmt'
        command_list = ['python /home/eserv/perforce/splunk/current/new_test/bin/pytest/pytest.py', '-v']
        proc = subprocess.Popen(command_list, shell=True, cwd=test_dir,
                         bufsize=0, stdin=subprocess.PIPE,
                         stdout=None, stderr=None, close_fds=True)
        proc.communicate()

        subprocess.call(['/usr/bullseye/bin/cov01', '-0']) 
        generate_reports(full_covfile, branch_path)
        # Stop Splunk to be removed
        subprocess.call([splunk_bin, 'stop'])
    print '/bin/tar' + ' -rf' + ' /home/eserv/bullseye_reports/bullseye-%s.tar' % branch + ' ' + full_path + ' --exclude=*.cov'
    subprocess.call(['/bin/tar', '-rf', 
                     '/home/eserv/bullseye_reports/bullseye-%s.tar' % branch, full_path,
                     '--exclude=*.cov'])

def updateYamlFile(path, new_file):
    import yaml
    stream = open(os.path.join(path, new_file), 'r')
    input = yaml.load(stream)
    input['peer1']['sshUser'] = 'eserv'
    input['peer2']['sshUser'] = 'eserv'
    input['head']['sshUser'] = 'eserv'
    new_file_path = os.path.join(path, 'bamboo-self-all-eserv.yml')
    stream = file(new_file_path, 'w')
    yaml.dump(input, stream)

if __name__ == '__main__':
    main(sys.argv[1:])
