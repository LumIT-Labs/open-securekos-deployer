import subprocess

class Process:
    @staticmethod
    # Execute process and get its exit code and output.
    # Wrapping C/Bash exit status convention to Python True/False for "success".
    def execute(invocation):
        execution = {
            "success": False,
            "status": 1,
            "output": ""
        }

        try:
            sbprc = subprocess.Popen(invocation, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Process std. output and std. error.
            execution["output"] = str(sbprc.stdout.readline()).strip()

            # Process exit code.
            streamdata = sbprc.communicate()[0]
            execution["status"] = int(sbprc.returncode)
            if execution["status"]==0:
                execution["success"] = True
        except Exception:
            pass

        return execution



    @staticmethod
    # Launch process and forget about it.
    def launch(invocation):
        subprocess.Popen(invocation, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return 0
