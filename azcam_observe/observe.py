"""
Observe class.

Notes:
IPython config needs:
 c.InteractiveShellApp.gui = 'qt'
 c.InteractiveShellApp.pylab = 'qt'
"""

import os
import time

import azcam


class Observe(object):
    """
    The Observe class which implements observing scripts.
    """

    def __init__(self):

        super().__init__()

        self.debug = 0  #: True to NOT execute commands
        self._abort_gui = 0  #: internal abort flag to stop
        self.verbose = 1  #: True to print commands during run()
        self.number_cycles = 1  #: Number of times to run the script.
        self.move_telescope_during_readout = 0  #: True to move the telescope during camera readout
        self.increment_status = 0  #: True to increment status count if command in completed

        self.script_file = ""  #: filename of observing commands cript file
        self.out_file = ""  #: output file showing executed commands

        self.lines = []
        self.commands = []  # list of dictionaries for each command to be executed
        self.current_line = -1  # current line being executed

        self.current_filter = ""  # current filter

        self._abort_script = 0  #: internal abort flag to stop scipt

        self.data = []  # list of dictionaries for each command to be executed

        # focus component for motion - instrument or telescope
        self.focus_component = "instrument"

        self.gui_mode = 0

    def initialize(self):
        """
        Initialize observe.
        """

        return

    def help(self):
        """
        Print help on scripting commands.
        """

        print("Observe class help...")
        print("")
        print('Always use double quotes (") when needed')
        print("")
        print("Comment lines start with # or !")
        print("")
        print("obs        ExposureTime imagetype Title NumberExposures Filter RA DEC Epoch")
        print("test       ExposureTime imagetype Title NumberExposures Filter RA DEC Epoch")
        print("")
        print("stepfocus  RelativeNumberSteps")
        print("steptel    RA_ArcSecs Dec_ArcSecs")
        print("movetel    RA Dec Epoch")
        print("movefilter FilterName")
        print("")
        print("delay      NumberSecs")
        print('print      hi there"')
        print('prompt     "press any key to continue..."')
        print("quit       quit script")
        print("")
        print("Script line examples:")
        print('obs 10.5 object "M31 field F" 1 u 00:36:00 40:30:00 2000.0 ')
        print('obs 2.3 dark "mike test dark" 2 u')
        print("stepfocus 50")
        print("delay 3")
        print("stepfocus -50")
        print("steptel 12.34 12.34")
        print("# this is a comment line")
        print("! this is also a comment line")
        print("movetel 112940.40 +310030.0 2000.0")
        print("")

        return

    def _get_focus(self, focus_id: int = 0,) -> float:

        if self.focus_component == "instrument":
            return azcam.api.instrument.get_focus(focus_id)
        elif self.focus_component == "telescope":
            return azcam.api.telescope.get_focus(focus_id)

    def _set_focus(self, focus_value: float, focus_id: int = 0, focus_type: str = "absolute"):

        if self.focus_component == "instrument":
            return azcam.api.instrument.set_focus(focus_value, focus_id, focus_type)
        elif self.focus_component == "telescope":
            return azcam.api.telescope.set_focus(focus_value, focus_id, focus_type)

    def read_file(self, script_file):
        """
        Read an observing script file.

        :param script_file: full path name of script file. If 'prompt', then ask for filename.
        :return: None
        """

        self.script_file = script_file

        # make output filename by appending _out to base filename
        base, ext = os.path.splitext(self.script_file)
        self.out_file = base + "_out" + ext

        # read file
        with open(self.script_file, "r") as sfile:
            all_lines = sfile.readlines()

        # save all lines
        self.lines = []
        self.commands = []  # list of dictionaries, one for each line
        for line in all_lines:
            if line == "\n":
                continue
            line = line.strip()
            self.lines.append(line)

        return

    def parse(self):
        """
        Parse current line set into self.commands dictionary.
        The script file must have already been read using read_file().

        :return: None
        """

        for linenumber, line in enumerate(self.lines):

            expose_flag = 0
            movetel_flag = 0
            steptel_flag = 0
            movefilter_flag = 0
            movefocus_flag = 0
            wave = ""
            focus = ""
            ra = ""
            dec = ""
            raNext = ""
            decNext = ""
            epoch = ""
            exptime = 0.0
            imagetype = ""
            arg = ""
            title = ""
            numexposures = 0
            status = 0

            tokens = azcam.utils.parse(line)

            # comment line, special case
            if line.startswith("#") or line.startswith("!") or line.startswith("comment"):
                cmd = "comment"
                arg = line[1:].strip()

            # if the first token is a number, it is a status flag - save and remove from parsing
            elif tokens[0].isdigit():
                status = int(tokens[0])
                line = line.lstrip(tokens[0]).strip()
                tokens = tokens[1:]  # reset tokens to not include status
                cmd = tokens[0].lower()
            else:
                status = -1  # indicates no status value
                cmd = tokens[0].lower()

            # comment
            if cmd == "comment":
                pass

            # prompt, use quotes for string
            elif cmd == "prompt":
                arg = tokens[1]

            # print
            elif cmd == "print":
                arg = tokens[1]

            elif cmd == "prompt":
                arg = tokens[1]

            # issue a raw server which should be in single quotes
            elif cmd == "azcam":
                arg = tokens[1]

            # take a normal observation
            elif cmd == "obs":
                # obs 10.5 object "M31 field F" 1 U 00:36:00 40:30:00 2000.0
                exptime = float(tokens[1])
                imagetype = tokens[2]
                title = tokens[3].strip('"')  # remove double quotes
                numexposures = int(tokens[4])
                expose_flag = 1
                if len(tokens) > 5:
                    wave = tokens[5].strip('"')
                    movefilter_flag = 1
                if len(tokens) > 6:
                    ra = tokens[6]
                    dec = tokens[7]
                    if len(tokens) > 8:
                        epoch = tokens[8]
                    else:
                        epoch = 2000.0
                    movetel_flag = 1
                else:
                    ra = ""
                    dec = ""
                    epoch = ""
                    movetel_flag = 0

            # take test images
            elif cmd == "test":
                # test 10.5 object "M31 field F" 1 U 00:36:00 40:30:00 2000.0
                exptime = float(tokens[1])
                imagetype = tokens[2]
                title = tokens[3].strip('"')
                numexposures = int(tokens[4])
                expose_flag = 1
                if len(tokens) > 5:
                    wave = tokens[5].strip('"')
                    movefilter_flag = 1
                if len(tokens) > 6:
                    ra = tokens[6]
                    dec = tokens[7]
                    if len(tokens) > 8:
                        epoch = tokens[8]
                    else:
                        epoch = 2000.0
                    movetel_flag = 1
                else:
                    ra = ""
                    dec = ""
                    epoch = ""
                    movetel_flag = 0

            # move focus position in relative steps from current position
            elif cmd == "stepfocus":
                # stepfocus RelativeSteps
                focus = float(tokens[1])
                # reply=step_focus(focus)
                movefocus_flag = 1

            # move filter
            elif cmd == "movefilter":
                # movefilter FilterName
                wave = tokens[1]
                movefilter_flag = 1

            # move telescope to absolute RA DEC EPOCH
            elif cmd == "movetel":
                # movetel ra dec
                ra = tokens[1]
                dec = tokens[2]
                epoch = tokens[3]
                movetel_flag = 1

            # slew telescope to absolute RA DEC EPOCH
            elif cmd == "slewtel":
                # slewtel ra dec
                ra = tokens[1]
                dec = tokens[2]
                epoch = tokens[3]
                movetel_flag = 1

            # move telescope relative RA DEC
            elif cmd == "steptel":
                # steptel raoffset decoffset
                raoffset = tokens[1]
                decoffset = tokens[2]
                ra = raoffset
                dec = decoffset
                movetel_flag = 1

            # delay N seconds
            elif cmd == "delay":
                delay = float(tokens[1])
                arg = delay

            # quit script
            elif cmd == "quit":
                pass

            else:
                azcam.log("command not recognized on line %03d: %s" % (linenumber, cmd))

            # get next RA and DEC if next line is obs command
            raNext = ""
            decNext = ""
            epochNext = ""
            if linenumber == len(self.lines) - 1:  # last line
                pass
            else:
                lineNext = self.lines[linenumber + 1]
                tokensNext = azcam.utils.parse(lineNext)
                lentokNext = len(tokensNext)
                if lentokNext != 0:
                    cmdNext = tokensNext[0].lower()
                    if cmdNext == "obs" and lentokNext > 6:
                        raNext = tokensNext[6]
                        decNext = tokensNext[7]
                        epochNext = tokensNext[8]
                    else:
                        pass

            data1 = {}
            data1["line"] = line
            data1["cmdnumber"] = linenumber
            data1["status"] = status
            data1["command"] = cmd
            data1["argument"] = arg
            data1["exptime"] = exptime
            data1["type"] = imagetype
            data1["title"] = title
            data1["numexp"] = numexposures
            data1["filter"] = wave
            data1["focus"] = focus
            data1["ra"] = ra
            data1["dec"] = dec
            data1["ra_next"] = raNext
            data1["dec_next"] = decNext
            data1["epoch"] = epoch
            data1["expose_flag"] = expose_flag
            data1["movetel_flag"] = movetel_flag
            data1["steptel_flag"] = steptel_flag
            data1["movefilter_flag"] = movefilter_flag
            data1["movefocus_flag"] = movefocus_flag
            self.commands.append(data1)

        return

    def log(self, message):
        """
        Log a message.
        :param message: string to be logged.
        :return: None
        """

        azcam.log(message)

        return

    def run(self):
        """
        Execute the commands in the script command dictionary.

        :return: None
        """

        self._abort_script = 0

        # save pars to be changed
        impars = {}
        azcam.utils.save_imagepars(impars)

        # log start info
        s = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log("Observing script started: %s" % s)

        # begin execution loop
        offsets = []
        for loop in range(self.number_cycles):

            if self.number_cycles > 1:
                self.log("*** Script cycle %d of %d ***" % (loop + 1, self.number_cycles))

            # open output file
            with open(self.out_file, "w") as ofile:
                if not ofile:
                    azcam.utils.restore_imagepars(impars)
                    self.log("could not open script output file %s" % self.out_file)
                    azcam.AzcamWarning("could not open script output file")
                    return

                for linenumber, command in enumerate(self.commands):

                    stop = 0

                    line = command["line"]
                    status = command["status"]

                    self.log("Command %03d/%03d: %s" % (linenumber, len(self.commands), line))

                    # execute the command
                    reply = self.execute_command(linenumber)

                    keyhit = azcam.utils.check_keyboard(0)
                    if keyhit == "q":
                        reply = "QUIT"
                        stop = 1

                    if reply == "STOP":
                        self.log("STOP after line %d" % linenumber)
                        stop = 1
                    elif reply == "QUIT":
                        stop = 1
                        self.log("QUIT after line %d" % linenumber)
                    else:
                        self.log("Reply %03d: %s" % (linenumber, reply))

                    # update output file and status
                    if command["command"] in [
                        "comment",
                        "print",
                        "delay",
                        "prompt",
                        "quit",
                    ]:  # no status
                        ofile.write("%s " % line + "\n")
                    elif self.increment_status:  # add status if needed
                        if status == -1:
                            status = 0
                        if stop:
                            ofile.write("%s " % status + line + "\n")
                        else:
                            ofile.write("%s " % (status + 1) + line + "\n")
                    else:
                        if stop:  # don't inc on stop
                            ofile.write("%s " % line + "\n")
                        else:
                            if status == -1:
                                ofile.write("%s " % line + "\n")
                            else:
                                ofile.write("%s " % (status) + line + "\n")

                    if stop or self._abort_script:
                        break

                    # check for pause
                    if self.gui_mode:
                        while self._paused:
                            self.wait4highlight()
                            time.sleep(1)

                # write any remaining lines to output file
                for i in range(linenumber + 1, len(self.commands)):
                    line = self.commands[i]["line"]
                    line = line.strip()
                    ofile.write(line + "\n")

        # finish
        azcam.utils.restore_imagepars(impars)
        self._abort_script = 0  # clear abort status

        return

    def execute_command(self, linenumber):
        """
        Execute one command.

        :param linenumber: Line number to execute, from command buffer.
        """

        # wait for highlighting of current row
        if self.gui_mode:
            self.current_line = linenumber
            self.wait4highlight()

        command = self.commands[linenumber]
        if self.debug:
            time.sleep(0.5)
            return "OK"

        reply = "OK"

        expose_flag = 0
        movetel_flag = 0
        steptel_flag = 0
        movefilter_flag = 0
        movefocus_flag = 0
        wave = ""
        ra = ""
        dec = ""
        epoch = ""
        exptime = ""
        imagetype = ""
        arg = ""
        title = ""
        numexposures = ""
        status = 0

        # get command and all parameters
        line = command["line"]
        cmd = command["command"]

        status = command["status"]
        arg = command["argument"]
        exptime = command["exptime"]
        imagetype = command["type"]
        title = command["title"]
        numexposures = command["numexp"]
        wave = command["filter"]
        ra = command["ra"]
        dec = command["dec"]
        raNext = command["ra_next"]
        decNext = command["dec_next"]
        epoch = command["epoch"]
        epochNext = command["epoch"]  # debug
        expose_flag = command["expose_flag"]
        movetel_flag = command["movetel_flag"]
        steptel_flag = command["steptel_flag"]
        movefilter_flag = command["movefilter_flag"]
        movefocus_flag = command["movefocus_flag"]

        exptime = float(exptime)
        numexposures = int(numexposures)
        expose_flag = int(expose_flag)
        movetel_flag = int(movetel_flag)
        steptel_flag = int(steptel_flag)
        movefilter_flag = int(movefilter_flag)
        movefocus_flag = int(movefocus_flag)

        # perform some immediate actions

        # comment
        if cmd == "comment":  # do nothing
            return "OK"

        elif cmd == "obs":
            pass

        elif cmd == "test":
            pass

        elif cmd == "offset":
            pass

        elif cmd == "stepfocus":
            reply = azcam.api.step_focus(arg)

        elif cmd == "movefilter":
            pass

        elif cmd == "movetel":
            pass

        # display message and then change command, for now
        elif cmd == "slewtel":
            cmd = "movetel"
            self.log("Enable slew for next telescope motion")
            reply = azcam.utils.prompt("Waiting...")
            return "OK"

        elif cmd == "steptel":
            self.log("offsetting telescope in arcsecs - RA: %s, DEC: %s" % (raoffset, decoffset))
            try:
                reply = azcam.api.server.rcommand(f"telescope.offset {raoffset} {decoffset}")
                return "OK"
            except azcam.AzcamError as e:
                return f"ERROR {e}"

        elif cmd == "delay":
            time.sleep(float(arg))
            return "OK"

        elif cmd == "azcam":
            try:
                reply = azcam.api.server.rcommand(arg)
                return reply
            except azcam.AzcamError as e:
                return f"ERROR {e}"

        elif cmd == "print":
            self.log(arg)
            return "OK"

        elif cmd == "prompt":
            self.log("prompt not available: %s" % arg)
            return "OK"

        elif cmd == "quit":
            self.log("quitting...")
            return "QUIT"

        else:
            self.log("script command %s not recognized" % cmd)

        # perform actions based on flags

        # move focus
        if movefocus_flag:
            self.log("Moving to focus: %s" % focus)
            if not self.DummyMode:
                reply = self._set_focus(focus)
                # reply, stop = check_exit(reply, 1)
                stop = self._abort_gui
                if stop:
                    return "STOP"
                reply = self._get_focus()
                self.log("Focus reply:: %s" % repr(reply))
                # reply, stop = check_exit(reply, 1)
                stop = self._abort_gui
                if stop:
                    return "STOP"

        # set filter
        if movefilter_flag:
            if wave != self.current_filter:
                self.log("Moving to filter: %s" % wave)
                if not self.debug:
                    azcam.api.instrument.set_filter(wave)
                    reply = azcam.api.instrument.get_filter()
                    self.current_filter = reply
            else:
                self.log("Filter %s already in beam" % self.current_filter)

        # move telescope to RA and DEC
        if movetel_flag:
            self.log("Moving telescope now to RA: %s, DEC: %s" % (ra, dec))
            if not self.debug:
                try:
                    reply = azcam.api.server.rcommand(f"telescope.move {ra} {dec} {epoch}")
                except azcam.AzcamError as e:
                    return f"ERROR {e}"

        # make exposure
        if expose_flag:
            for i in range(numexposures):
                if steptel_flag:
                    self.log(
                        "Offsetting telescope in RA: %s, DEC: %s"
                        % (offsets[i * 2], offsets[i * 2 + 1])
                    )
                    if not self.debug:
                        reply = TelescopeOffset(offsets[i * 2], offsets[i * 2 + 1])
                        # reply, stop = check_exit(reply, 1)
                        stop = self._abort_gui
                        if stop:
                            return "STOP"

                if cmd != "test":
                    azcam.api.config.set_par("imagetest", 0)
                else:
                    azcam.api.config.set_par("imagetest", 1)
                filename = azcam.api.exposure.get_image_filename()

                if cmd == "test":
                    self.log(
                        "test %s: %d of %d: %.3f sec: %s"
                        % (imagetype, i + 1, numexposures, exptime, filename)
                    )
                else:
                    self.log(
                        "%s: %d of %d: %.3f sec: %s"
                        % (imagetype, i + 1, numexposures, exptime, filename)
                    )

                if self.move_telescope_during_readout and (raNext != ""):

                    if i == numexposures - 1:  # Apr15
                        doMove = 1
                    else:
                        doMove = 0

                    if 1:
                        # if not self.debug:
                        reply = azcam.api.exposure.expose1(
                            exptime, imagetype, title
                        )  # immediate return
                        time.sleep(2)  # wait for Expose process to start
                        cycle = 1
                        while 1:
                            flag = azcam.api.config.get_par("ExposureFlag")
                            if flag is None:
                                self.log("Could not get exposure status, quitting...")
                                stop = 1
                                return "STOP"
                            if (
                                flag == azcam.db.exposureflags["EXPOSING"]
                                or flag == azcam.db.exposureflags["SETUP"]
                            ):
                                flagstring = "Exposing"
                            elif flag == azcam.db.exposureflags["READOUT"]:
                                flagstring = "Reading"
                                if doMove:
                                    check_header = 1
                                    while check_header:
                                        header_updating = int(
                                            azcam.api.config.get_par("exposureupdatingheader")
                                        )
                                        if header_updating:
                                            self.log("Waiting for header to finish updating...")
                                            time.sleep(0.5)
                                        else:
                                            check_header = 0
                                    self.log(
                                        "Moving telescope to next field - RA: %s, DEC: %s"
                                        % (raNext, decNext)
                                    )
                                    try:
                                        reply = azcam.api.server.rcommand(
                                            "telescope.move_start %s %s %s"
                                            % (raNext, decNext, epochNext)
                                        )
                                    except azcam.AzcamError as e:
                                        return f"ERROR {e}"
                                    doMove = 0
                            elif flag == azcam.db.exposureflags["WRITING"]:
                                flagstring = "Writing"
                            elif flag == azcam.db.exposureflags["NONE"]:
                                flagstring = "Finished"
                                break
                            # self.log('Checking Exposure Status (%03d): %10s\r' % (cycle,flagstring))
                            time.sleep(0.1)
                            cycle += 1
                else:
                    if not self.debug:
                        azcam.api.exposure.expose(exptime, imagetype, title)

                # reply, stop = check_exit(reply)
                stop = self._abort_gui
                if stop:
                    return "STOP"

                keyhit = azcam.utils.check_keyboard(0)
                if keyhit == "q":
                    return "QUIT"

        return "OK"
