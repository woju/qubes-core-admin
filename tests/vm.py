#!/usr/bin/python2 -O

import sys
import unittest

import lxml.etree

sys.path.insert(0, '../')
import qubes.vm


class TestVM(qubes.vm.BaseVM):
    qid = qubes.property('qid', type=int)
    name = qubes.property('name')
    testprop = qubes.property('testprop')
    testlabel = qubes.property('testlabel')
    defaultprop = qubes.property('defaultprop', default='defaultvalue')

class TC_BaseVM(unittest.TestCase):
    def setUp(self):
        self.xml = lxml.etree.XML('''
<qubes version="3"> <!-- xmlns="https://qubes-os.org/QubesXML/1" -->
    <labels>
        <label id="label-1" color="#cc0000">red</label>
    </labels>

    <domains>
        <domain id="domain-1" class="TestVM">
            <properties>
                <property name="qid">1</property>
                <property name="name">domain1</property>
                <property name="testprop">testvalue</property>
                <property name="testlabel" ref="label-1" />
            </properties>

            <tags>
                <tag name="testtag">tagvalue</tag>
            </tags>

            <services>
                <service>testservice</service>
                <service enabled="True">enabledservice</service>
                <service enabled="False">disabledservice</service>
            </services>

            <devices class="pci">
                <device>00:11.22</device>
            </devices>

            <devices class="usb" />
            <devices class="audio-in" />
            <devices class="firewire" />
            <devices class="i2c" />
            <devices class="isa" />
        </domain>
    </domains>
</qubes>
        ''')

    def test_000_BaseVM_load(self):
        node = self.xml.xpath('//domain')[0]
        vm = TestVM.fromxml(None, node)

        self.assertEqual(vm.qid, 1)
        self.assertEqual(vm.testprop, 'testvalue')
        self.assertEqual(vm.testprop, 'testvalue')
        self.assertEqual(vm.testlabel, 'label-1')
        self.assertEqual(vm.defaultprop, 'defaultvalue')
        self.assertEqual(vm.tags, {'testtag': 'tagvalue'})
        self.assertEqual(vm.devices, {'pci': ['00:11.22']})
        self.assertEqual(vm.services, {
            'testservice': True,
            'enabledservice': True,
            'disabledservice': False,
        })

        lxml.etree.ElementTree(vm.__xml__()).write(sys.stderr, encoding='utf-8', pretty_print=True)

    def test_001_BaseVM_nxproperty(self):
        xml = lxml.etree.XML('''
<qubes version="3">
    <domains>
        <domain id="domain-1" class="TestVM">
            <properties>
                <property name="nxproperty">nxvalue</property>
            </properties>
        </domain>
    </domains>
</qubes>
        ''')

        node = xml.xpath('//domain')[0]

        with self.assertRaises(AttributeError):
            TestVM.fromxml(None, node)
