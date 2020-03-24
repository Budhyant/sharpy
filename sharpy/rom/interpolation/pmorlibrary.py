"""
ROM Interpolation library interface
"""
import glob
import pickle
import configobj
import sharpy.utils.cout_utils as coututils
import os
import numpy as np
import sharpy.linear.src.libss as libss
import scipy.linalg as sclalg

coututils.start_writer()
coututils.cout_wrap.cout_talk()


class ROMLibrary:
    """
    Create, load, save, append ROMs to a library

    """

    def __init__(self):
        self.library_name = None
        self.folder = None
        self.library = None

        self.data_library = None

        self.reference_case = None

        self.parameters = None
        self.param_values = None
        self.mapping = None
        self.parameter_index = None
        self.inverse_mapping = None

    def interface(self):

        while True:
            user_input = self.main_menu()

            if user_input == 0:
                break

            elif user_input == 1:
                self.create()

            elif user_input == 2:
                self.load_library()

            elif user_input == 3:
                self.save_library()

            elif user_input == 4:
                self.load_case(input('Path to SHARPy output folder: '))

            elif user_input == 5:
                self.display_library()

            elif user_input == 6:
                self.delete_case()

            elif user_input == 7:
                self.set_reference_case()

            else:
                coututils.cout_wrap('Input not recognised', 3)

    def create(self, settings=None):

        if settings is None:
            self.get_library_name()
            # look for pickles and configs
            pickle_source_path = input('Enter path to folder containing ROMs (in .pkl): ')
        else:
            self.library_name = settings.get('library_name', None)
            self.folder = settings.get('folder', None)
            pickle_source_path = settings['pickle_source_path']

        self.library = []

        self.load_files(pickle_source_path)

    def get_library_name(self):
        self.library_name = input('Enter library name: ')
        self.folder = input('Enter path to folder: ')

    def load_files(self, path):

        sharpy_cases = glob.glob(path + '/*')

        coututils.cout_wrap('Loading cases from SHARPy cases in %s' % os.path.abspath(path) + '/')

        if len(sharpy_cases) == 0:
            coututils.cout_wrap('Unable to find any SHARPy cases. Please use interface', 3)
            self.interface()

        for case in sharpy_cases:
            self.load_case(case)

    def load_case(self, case_path):

        coututils.cout_wrap('Loading %s' % os.path.abspath(case_path))

        # load pmor
        pmor_path = glob.glob(case_path + '/*.pmor*')
        if len(pmor_path) != 0:
            pmor_case_data = configobj.ConfigObj(pmor_path[0])

            dict_params = dict()
            for item in pmor_case_data['parameters']:
                dict_params[item] = float(pmor_case_data['parameters'][item])

            try:
                case_name = pmor_case_data['sim_info']['case']
                path_to_data = glob.glob(pmor_case_data['sim_info']['path_to_data'] + '/*.pkl')
                try:
                    self.library.append({'case': case_name, 'path_to_data': path_to_data[0], 'parameters': dict_params})
                except IndexError:
                    coututils.cout_wrap('Unable to locate pickle file containing case data %s' % path_to_data, 4)
            except KeyError:
                coututils.cout_wrap('File not in correct format', 4)
        else:
            coututils.cout_wrap('Unable to locate .pmor.sharpy config file with parameter information', 4)

    def save_library(self):
        if self.library is not None:
            path = self.folder + '/' + self.library_name + '.pkl'
            pickle.dump((self.library, self.reference_case), open(path, 'wb'))
            coututils.cout_wrap('Saved library to %s' % os.path.abspath(self.folder), 2)

    def load_library(self, path=None):
        if path is None:
            self.get_library_name()
            path = self.folder + '/' + self.library_name + '.pkl'
        try:
            self.library, self.reference_case = pickle.load(open(path, 'rb'))
            coututils.cout_wrap('Successfully loaded library from %s' % path, 2)
        except FileNotFoundError:
            coututils.cout_wrap('Unable to find library at %s' % path, 3)
            self.interface()

    def display_library(self):

        if len(self.library) == 0:
            coututils.cout_wrap('Libary is empty. Nothing to display', 3)
        else:
            params = self.library[0]['parameters'].keys()

            library_table = coututils.TablePrinter(n_fields=len(params) + 2,
                                                   field_types=['g'] + ['g'] * len(params) + ['s'],
                                                   field_length=[4] + len(params) * [12] + [90])
            library_table.print_header(field_names=['no'] + list(params) + ['Case Name'])
            [library_table.print_line([ith] + list(entry['parameters'].values()) + [entry['case']])
             for ith, entry in enumerate(self.library)]
            library_table.print_divider_line()

            coututils.cout_wrap('Reference case: %s' % str(self.reference_case))

    def delete_case(self):
        self.display_library()

        del_index = self.select_from_menu()

        try:
            del self.library[del_index]
            coututils.cout_wrap('Deleted case successfully', 2)
        except IndexError:
            coututils.cout_wrap('Index out of range. Unable to remove', 3)

    def set_reference_case(self, reference_case=None):

        if reference_case is None:
            self.display_library()
            reference_case = self.select_from_menu(input_message='Select reference case: ')

        if reference_case in range(len(self.library)):
            self.reference_case = reference_case
        else:
            coututils.cout_wrap('Index Error. Unable to set reference case to desired index', 4)

    def main_menu(self):
        coututils.cout_wrap("\n-------------------------------\n"
                            "PMOR Library Interface Menu\n"
                            "-------------------------------\n\n"
                            "[1] - Create library\n"
                            "[2] - Load library\n"
                            "[3] - Save library\n"
                            "[4] - Add case to library\n"
                            "[5] - Display library\n"
                            "[6] - Delete case")

        if self.reference_case is None and self.library is not None:
            ref_color = 1
        else:
            ref_color = 0

        coututils.cout_wrap('[7] - Set reference case\n', ref_color)

        coututils.cout_wrap("\n[0] - Quit")

        return self.select_from_menu()

    def load_data_from_library(self):

        self.data_library = []

        for case in self.library:
            with open(case['path_to_data'], 'rb') as f:
                case_data = pickle.load(f)
            self.data_library.append(case_data)

    def get_reduced_order_bases(self, target_system):
        """
        Returns the bases and state spaces of the chosen systems.

        To Do: find system regardless of MOR method

        Returns:
            tuple: list of state spaces, list of right ROBs and list of left ROBs
        """

        assert self.data_library is not None, 'ROM Library is empty. Load the data first.'

        if target_system == 'uvlm':
            ss_list = [rom.linear.linear_system.uvlm.ss for rom in self.data_library]
            vv_list = [rom.linear.linear_system.uvlm.rom['Krylov'].V for rom in self.data_library]
            wwt_list = [rom.linear.linear_system.uvlm.rom['Krylov'].W.T for rom in self.data_library]

        elif target_system == 'aeroelastic':
            ss_list = []
            vv_list = []
            wwt_list = []
            for rom in self.data_library:
                vv = sclalg.block_diag(rom.linear.linear_system.uvlm.rom['Krylov'].V,
                                       np.eye(rom.linear.linear_system.beam.ss.states))
                wwt = sclalg.block_diag(rom.linear.linear_system.uvlm.rom['Krylov'].W.T,
                                        np.eye(rom.linear.linear_system.beam.ss.states))
                ss_list.append(rom.linear.ss)
                vv_list.append(vv)
                wwt_list.append(wwt)

        elif target_system == 'structural':
            raise NotImplementedError

        else:
            raise NameError('Unrecognised system on which to perform interpolation')

        return ss_list, vv_list, wwt_list

    def sort_grid(self):

        param_library = [case['parameters'] for case in self.library]
        parameters = list(param_library[0].keys())  # all should have the same parameters
        param_values = [[case[param] for case in param_library] for param in parameters]

        parameter_index = {parameter: ith for ith, parameter in enumerate(parameters)}

        # sort parameters
        [parameter_values.sort() for parameter_values in param_values]
        parameter_values = [f7(item) for item in param_values]  # TODO: rename these variables

        inverse_mapping = np.empty([len(parameter_values[n]) for n in range(len(parameters))], dtype=int)
        mapping = []
        i_case = 0
        for case_parameters in param_library:
            current_case_mapping = []
            for ith, parameter in enumerate(parameters):
                p_index = parameter_values[ith].index(case_parameters[parameter])
                current_case_mapping.append(p_index)
            mapping.append(current_case_mapping)
            inverse_mapping[tuple(current_case_mapping)] = i_case
            i_case += 1

        self.parameters = parameters
        self.param_values = parameter_values  # TODO: caution -- rename
        self.mapping = mapping
        self.parameter_index = parameter_index
        self.inverse_mapping = inverse_mapping

    @staticmethod
    def select_from_menu(input_message='Select option: ',
                         unrecognised_message='Unrecognised input choice'):

        try:
            user_input = int(input('\n' + input_message))
        except ValueError:
            coututils.cout_wrap(unrecognised_message, 3)
            user_input = -1
        return user_input

    def retrieve_fom(self, rom_index):
        # TODO: search for FOM other than in the Krylov case...
        ss_fom_aero = self.data_library[rom_index].linear.linear_system.uvlm.rom['Krylov'].ss
        ss_fom_beam = self.data_library[rom_index].linear.linear_system.beam.ss

        Tas = np.eye(ss_fom_aero.inputs, ss_fom_beam.outputs)
        Tsa = np.eye(ss_fom_beam.inputs, ss_fom_aero.outputs)

        ss = libss.couple(ss_fom_aero, ss_fom_beam, Tas, Tsa)

        return ss

class InterpolatedROMLibrary:
    """
    Library of interpolated ROMs for storage in PreSHARPy object

    Attributes:
        ss_list (list): List of interpolated :class:`~sharpy.linear.src.libss.ss`
        parameter_list (list(dict)): List of dictionaries corresponding to the parameters at which the state-spaces
          were interpolated.
    """

    def __init__(self, ss_list=list(), parameter_list=list()):

        self.ss_list = ss_list
        self.parameter_list = parameter_list

    def append(self, interpolated_ss, parameters):
        """
        Add entry to library

        Args:
            interpolated_ss (sharpy.linear.src.libss.ss): Interpolated system.
            parameters (dict): Dictionary with parameters at which system was interpolated.
        """

        self.ss_list.append(interpolated_ss)
        self.parameter_list.append(parameters)

    def write_summary(self, filename):

        summary = configobj.ConfigObj()
        summary.filename = filename

        for ith, case in enumerate(self.parameter_list):
            case_number = 'case_%02g' % ith
            summary[case_number] = case

        summary.write()

    def load_previous_cases(self, filename):

        try:
            summary = configobj.ConfigObj(filename)
            for entry in summary:
                current_case = dict()
                for parameter in summary[entry]:
                    current_case[parameter] = float(summary[entry][parameter])
                self.parameter_list.append(current_case)

        except OSError:
            coututils.cout_wrap('Unable to load summary file containing info on previous cases', 3)

    @property
    def case_number(self):
        return len(self.parameter_list)

def f7(seq):
    """
    Adds single occurrences of an item in a list
    """
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

if __name__ == '__main__':
    ROMLibrary().interface()
