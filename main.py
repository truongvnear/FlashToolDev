import os
import subprocess
import sys
import time
import fileinput
import re

BT_ADDR_PATTERN = "BD_ADDRESS = [ "
DEVICE_NAME_PATTERN = "DeviceName = "
FW_VER_PATTERN = "CUSTOMER88 ="
SERIAL_NO_PATTERN = "CUSTOMER0 ="

SUCCESS = "Success"
FAILED = "Failed"
PROCESSING = "Processing"

STATUS_SUCCESS = 0
STATUS_FAILED = 1
STATUS_PROCESSING = 2

status = [SUCCESS, FAILED, PROCESSING]

_cur_module_path    = os.path.realpath(__file__)
_cur_module_dir     = os.path.dirname(_cur_module_path)
_cur_module_name    = os.path.basename(_cur_module_path)


def is_hex(s):
    return re.search(r'^[0-9A-Fa-f]+$', s or "") is not None


def print_format(s: str, state: int):
    global status
    if state != STATUS_PROCESSING:
        sys.stdout.write("\033[F")
        sys.stdout.write("\033[K")
        print('\r{0: <50}: '.format(s) + status[state])
    else:
        print('{0: <50}: '.format(s) + status[state])


def print_format_bool(s: str, state: bool):
    if state:
        print_format(s, STATUS_SUCCESS)
    else:
        print_format(s, STATUS_FAILED)


def print_tag(s: str):
    s_len = len(s)
    delimiter_nums: int = 0
    if s_len % 2:
        delimiter_nums = (60 - s_len - 1)//2
        print("="*delimiter_nums + s + "="*(delimiter_nums+1))
    else:
        delimiter_nums = (60 - s_len)//2
        print("=" * delimiter_nums + s + "=" * (delimiter_nums))


def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    # return_code = popen.wait()
    # if return_code:
    #     raise subprocess.CalledProcessError(return_code, cmd)


def mt_get_program_directory() -> str:
    application_path = ""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)
    return application_path


def mt_cfg_parse_device_name(input_str: str) -> str:
    result = re.search("(?<=\").*?(?=\")", input_str)[0]
    return result


def mt_cfg_parse_bt_addr(input_str: str):
    result = re.search("(?<=\[).*?(?=\])", input_str)[0]
    return result.split()

def mt_cfg_parse_hex_array_to_str(input_str):
    result = re.search("(?<=\[).*?(?=\])", input_str)[0]
    result = result.replace(" ", "")
    return bytearray.fromhex(result).decode()

def mt_cfg_parse_fw_ver(input_str: str) -> str:
    result = re.search("(?<=\[).*?(?=\])", input_str)[0]
    result = result.replace(" ", "")
    return bytearray.fromhex(result).decode()


def mt_cfg_bt_addr_to_str(bt_addr: list) -> str:
    result = BT_ADDR_PATTERN
    for addr in bt_addr:
        result += addr
        result += " "
    result += "]"
    return result


def mt_cfg_serialno_to_device_name_str(serial_no):
    identifier = serial_no[5:8]
    return DEVICE_NAME_PATTERN + "\"AUDIO_FRENZ" + identifier + "\""


def mt_cfg_str_to_byte_array(input_str):
    output = []
    for c in input_str:
        output.append(c.encode('utf-8').hex())
    return output


def mt_cfg_serialno_to_str(serial_no):
    output_str = SERIAL_NO_PATTERN + "[ "
    output_array = mt_cfg_str_to_byte_array(serial_no)
    for output_byte in output_array:
        output_str += str(output_byte)
        output_str += " "
    output_str += "]"
    return output_str


def mt_cfg_device_name_to_str(device_name):
    return DEVICE_NAME_PATTERN + "\"" + device_name + "\""


class ManufactureTool(object):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.exit(0)

    def __init__(self):
        self.invalid_input: bool = False
        self.is_initialize: bool = True
        self.result = False

        self.bt_addr = ""
        self.device_name = ""
        self.fw_ver = ""
        self.hw_ver = ""
        self.serial_no = ""

        global _cur_module_dir
        _cur_module_dir = mt_get_program_directory()

        self.nvs_tool = os.path.join(_cur_module_dir, "lib", "NvsCmd.exe")
        self.config_tool = os.path.join(_cur_module_dir, "lib", "ConfigCmd.exe")
        self.sdb_file = os.path.join(_cur_module_dir, "db", "hydracore_config.sdb")
        self.cfg_dev_cfg = os.path.join(_cur_module_dir, "config", "dev_cfg")
        self.cfg_user_ps_apps = os.path.join(_cur_module_dir, "config", "user_ps_apps")

        if not self.mt_check_env():
            print("Can not find necessary files")
            input("Press any key to exit!!!")
            sys.exit(0)

    def mt_check_env(self) -> bool:
        print_format("Checking environment", STATUS_PROCESSING)
        if not os.path.exists(self.nvs_tool):
            print_format("Checking environment", STATUS_FAILED)
            print("Can not find nvscmd tool")
            return False

        if not os.path.exists(self.config_tool):
            print_format("Checking environment", STATUS_FAILED)
            print("Can not find configcmd tool")
            return False

        if not os.path.exists(self.sdb_file):
            print_format("Checking environment", STATUS_FAILED)
            print("Can not find database file")
            return False

        print_format("Checking environment", STATUS_SUCCESS)
        return True

    def mt_fl_identify(self) -> bool:
        print_format("Identify device", STATUS_PROCESSING)
        result = False

        args = self.nvs_tool + " -usbdbg 1 -deviceid 4 0 -nvstype sqif identify"
        for line in execute(args):
            print(line, end="")
            if SUCCESS in line:
                result = True
        return result

    def mt_fl_burn(self, fw_image_file_path: str) -> bool:
        print_format("Burning", STATUS_PROCESSING)
        result = False

        args = self.nvs_tool + " -usbdbg 1 -deviceid 4 0 -nvstype sqif burn " + fw_image_file_path
        for line in execute(args):
            print(line, end="")
            if SUCCESS in line:
                result = True
        print_format_bool("Burning", result)
        return result

    def mt_fl_flash_fw(self) -> bool:
        print_tag("FLASH")
        fw_path = input("Drag and drop flash_image.xuv here: ")
        if ".xuv" not in fw_path:
            print("Not recognize fw image")
            self.mt_fl_flash_fw()

        if not os.path.exists(fw_path):
            print("Can not find fw file")
            self.mt_fl_flash_fw()
        
        # Read current configuration from device (dev_cfg & user_ps_apps)
        # print_format("Recover device configurations", STATUS_PROCESSING)
        if not self.mt_cfg_load_config_from_device():
            print("Can not connect device")
            return False

        # print_format("Burn FW to device", STATUS_PROCESSING)
        if not self.mt_fl_burn(fw_path):
            return False

        is_device_available = False
        print_format("Reset device", STATUS_PROCESSING)
        time.sleep(5)
        print_format("Reset device", STATUS_SUCCESS)

        # Write configuration to device
        ret = self.mt_cfg_write_usr_ps_cfg()
        print("write usr_cfg " + str(ret))

        ret = self.mt_cfg_write_dev_cfg()
        print_format_bool("Recover device configurations", ret)

        return ret

    def mt_cfg_load_config_from_device(self) -> bool:
        dev_result = False
        usr_result = False

        print_format("Loading configuration from device", STATUS_PROCESSING)
        # Load dev_cfg
        args = self.config_tool + " dev2txt " + self.cfg_dev_cfg + " -storeset dev_cfg -usbdbg 1 -system QCC514X_CONFIG -database " + self.sdb_file
        # print(args)
        for line in execute(args):
            print(line, end="")
            if SUCCESS in line:
                dev_result = True

        # Load user_ps
        args = self.config_tool + " dev2txt " + self.cfg_user_ps_apps + " -storeset user_ps_apps -usbdbg 1 -system QCC514X_CONFIG -database " + self.sdb_file
        # print(args)
        for line in execute(args):
            print(line, end="")
            if SUCCESS in line:
                usr_result = True
        print_format_bool("Loading configuration from device", dev_result & usr_result)
        return dev_result & usr_result

    def mt_cfg_write_dev_cfg(self) -> bool:
        result = False
        args = self.config_tool + " txt2dev " + self.cfg_dev_cfg + " MERGE -storeset dev_cfg -usbdbg 1 -system QCC514X_CONFIG -reset -database " + self.sdb_file
        # print(args)        
        for line in execute(args):
            print(line, end="")
            if SUCCESS in line:
                result = True
        return result
    
    def mt_cfg_write_usr_ps_cfg(self):
        result = False
        args = self.config_tool + " txt2dev " + self.cfg_user_ps_apps + " MERGE -storeset user_ps_apps -usbdbg 1 -system QCC514X_CONFIG -database " + self.sdb_file
        # print(args)        
        for line in execute(args):
            # print(line, end="")
            if SUCCESS in line:
                result = True
        return result

    def mt_cfg_parse_dev_cfg(self):
        with open(self.cfg_dev_cfg) as file:
            for line in file:
                if BT_ADDR_PATTERN in line:
                    self.bt_addr = mt_cfg_parse_bt_addr(line)
                if DEVICE_NAME_PATTERN in line:
                    self.device_name = mt_cfg_parse_device_name(line)

    def mt_cfg_parse_user_ps(self):
        with open(self.cfg_user_ps_apps) as file:
            for line in file:
                if FW_VER_PATTERN in line:
                    self.fw_ver = mt_cfg_parse_fw_ver(line)
                if SERIAL_NO_PATTERN in line:
                    self.serial_no = mt_cfg_parse_hex_array_to_str(line)

    def mt_cfg_bt_prompt(self) -> str:
        # Change BT address (00->FF)
        bt_addr = input("Choose input address (hex value from 00 to FF): ")
        if len(bt_addr) > 2:
            return self.mt_cfg_bt_prompt()

        if not is_hex(bt_addr):
            self.mt_cfg_bt_prompt()
        return bt_addr.upper()

    def mt_cfg_change_bt_addr(self):
        # Ask user to new address
        bt_addr = self.mt_cfg_bt_prompt()
        print_format("Change bluetooth address", STATUS_PROCESSING)

        # Read current configuration from device (dev_cfg)
        self.mt_cfg_load_config_from_device()
        self.mt_cfg_parse_dev_cfg()

        print("Old BT Addr: " + str(self.bt_addr))
        self.bt_addr[0] = bt_addr
        print("New BT Addr: " + str(self.bt_addr) + "\n")

        with fileinput.FileInput(self.cfg_dev_cfg, inplace=True, backup='.bak') as file:
            for line in file:
                if BT_ADDR_PATTERN in line:
                    bd_addr = mt_cfg_bt_addr_to_str(self.bt_addr)
                    print(bd_addr)
                else:
                    print(line, end="")

        # Write configuration to device
        ret = self.mt_cfg_write_dev_cfg()
        print_format_bool("Change bluetooth address", ret)
        return ret

    def mt_cfg_change_sn_prompt(self) -> str:
        sn = input("Please in SN: ")
        if len(sn) != 14:
            return self.mt_cfg_change_sn_prompt()
        return sn.upper()

    def mt_cfg_change_sn(self) -> None:
        # Ask user to new address
        sn = self.mt_cfg_change_sn_prompt()
        print_format("Change SN", STATUS_PROCESSING)

        # Read current configuration from device (dev_cfg)


    def mt_cfg_device_name_prompt(self) -> str:
        device_name = input("Choose device name (1-60 letters): ")
        if len(device_name) < 1 or len(device_name) > 60:
            return self.mt_cfg_device_name_prompt()
        return device_name.upper()

    def validate_serialno(self, serialno):
        re1 = re.compile(r"[<>:/\\{}\[\]~`]")

        if re1.search(serialno):
            return False
        else:
            return True

    def mt_cfg_device_sn_prompt(self):
        serial_no = input("Enter Serial Number (12 chars): ")
        if (len(serial_no) != 12) or (not self.validate_serialno(serial_no)):
            print("Please check the S/N code again with the conditions:\n\t* The number of characters of the SN is 12 \n\t* And don't contain special characters. <>:/\{}[]~`")
            return self.mt_cfg_device_sn_prompt()
        return serial_no

    def mt_cfg_change_serial_no(self):
        # Ask user to new address
        serial_no = self.mt_cfg_device_sn_prompt()
        print_format("Write Serial Number", STATUS_PROCESSING)

        # Change device name and MAC address
        with fileinput.FileInput(self.cfg_dev_cfg, inplace=True, backup='.bak') as file:
            for line in file:
                if DEVICE_NAME_PATTERN in line:
                    device_name_str = mt_cfg_serialno_to_device_name_str(serial_no)
                    print(device_name_str)
                else:
                    print(line, end="")

        # Change Serial Number
        re_write_sn = False
        with fileinput.FileInput(self.cfg_user_ps_apps, inplace=True, backup='.bak') as file:
            for line in file:
                if SERIAL_NO_PATTERN in line:
                    re_write_sn = True
                    serial_no_str = mt_cfg_serialno_to_str(serial_no)
                    print(serial_no_str)
                else:
                    print(line, end="")

        if not re_write_sn:
            serial_no_str = mt_cfg_serialno_to_str(serial_no)
            f = open(self.cfg_user_ps_apps, "a")
            f.write("\n" + serial_no_str + "\n")
            f.close()

        # Write configuration to device
        
        ret = self.mt_cfg_write_usr_ps_cfg()
        print("write usr_cfg " + str(ret))

        ret &= self.mt_cfg_write_dev_cfg()
        print("write dev_cfg " + str(ret))

        # waiting reset device
        print_format("Reset device", STATUS_PROCESSING)
        time.sleep(5)
        print_format("Reset device", STATUS_SUCCESS)
        return ret

    def mt_cfg_change_device_name(self):
        # Ask user to new address
        device_name = self.mt_cfg_device_name_prompt()
        print_format("Change device name", STATUS_PROCESSING)

        # Read current configuration from device (dev_cfg)
        self.mt_cfg_load_config_from_device()
        self.mt_cfg_parse_dev_cfg()

        print("Old Device Name: " + str(self.device_name))
        self.device_name = device_name
        print("New Device Name: " + str(self.device_name) + "\n")

        with fileinput.FileInput(self.cfg_dev_cfg, inplace=True, backup='.bak') as file:
            for line in file:
                if DEVICE_NAME_PATTERN in line:
                    device_name = mt_cfg_device_name_to_str(self.device_name)
                    print(device_name)
                else:
                    print(line, end="")

        # Write configuration to device
        ret = self.mt_cfg_write_dev_cfg()
        print_format_bool("Change device name", ret)
        return ret

    """
    1. Display option prompt
    2. Classify the choice
    3a. Execute action depend on choice
    3b. Option invalid -> ask user re-choose
    """
    def mt_main_option(self):
        if self.is_initialize or self.invalid_input or not self.result:
            self.is_initialize = False
        else:
            print_format("Reset device", STATUS_PROCESSING)
            time.sleep(5)
            # subprocess.call('cls', shell=True)
            # print("\033c", end="")
            print_format("Reset device", STATUS_SUCCESS)

        # if not self.mt_fl_identify():
        #     print("Can not identify the device")
        #     input("Press any key to exit")
        #     sys.exit(0)
        #
        # time.sleep(5)
        if not self.mt_cfg_load_config_from_device():
            print("Can load device configurations\nPlease ensure device is on and connected to PC")
            input("Press any key to exit!!!")
            sys.exit(0)

        self.mt_cfg_parse_dev_cfg()
        self.mt_cfg_parse_user_ps()

        print_tag("DEVICE CONFIGURATION")
        print("Device Name: " + self.device_name)
        print("BT Address :  " + str(self.bt_addr))
        print("Serial No  :  " + str(self.serial_no))
        print("FW Version :  " + self.fw_ver)

        self.invalid_input = False
        print_tag("MAIN")
        choice = input("Choose Action:\n1.Flash FW\n2.Change Device Name\n3.Change Bluetooth Adress\n4.Change Serial Number\nYour choice: ")
        try:
            choice = int(choice)
        except ValueError:
            self.mt_main_option()

        if choice == 1:
            self.result = self.mt_fl_flash_fw()
        elif choice == 2:
            self.result = self.mt_cfg_change_device_name()
        elif choice == 3:
            self.result = self.mt_cfg_change_bt_addr()
        elif choice == 4:
            self.mt_cfg_change_serial_no()
        else:
            self.invalid_input = True

        self.mt_main_option()

    """
    1. Load configuration from current device
    2. Show device info (name, bt address, fw version)
    3. Ask user to choose option (flash or modify info)
    """
    def main(self):
        self.mt_main_option()


if __name__ == '__main__':
    with ManufactureTool() as mt:
        mt.main()

