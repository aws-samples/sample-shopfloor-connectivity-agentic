#!/usr/bin/env python3
"""
Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. SPDX-License-Identifier: MIT-0

AWS Shopfloor Connectivity (SFC) Configuration Generator
Provides functions for generating SFC configuration templates
"""

import json
from typing import Dict, Any


def generate_config_template(
    protocol: str, target: str, environment: str, sfc_knowledge: Dict[str, Any]
) -> str:
    """Generate a configuration template

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        environment: Environment type (development, production)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        String containing the generated configuration template
    """
    if protocol not in sfc_knowledge["supported_protocols"]:
        return f"❌ Unsupported protocol: {protocol}. Supported: {', '.join(sfc_knowledge['supported_protocols'].keys())}"

    # Create basic template structure
    template = {
        "AWSVersion": sfc_knowledge["aws_version"],
        "Name": f"{protocol} to {target} Configuration",
        "Description": f"{environment.title()} configuration for {protocol} protocol to {target} target",
        "LogLevel": "Info" if environment == "production" else "Trace",
        "Schedules": [
            {
                "Name": f"{protocol}Schedule",
                "Interval": 1000 if environment == "development" else 5000,
                "Active": True,
                "TimestampLevel": "Both",
                "Sources": {f"{protocol}-SOURCE": ["*"]},
                "Targets": [f"{target}Target"],
            }
        ],
        "Sources": generate_source_template(protocol, sfc_knowledge),
        "Targets": generate_target_template(target, environment, sfc_knowledge),
        "TargetTypes": generate_target_types(target, sfc_knowledge),
        "AdapterTypes": generate_adapter_types(protocol, sfc_knowledge),
        "ProtocolAdapters": generate_protocol_adapter_config(protocol, sfc_knowledge),
    }

    return f"✅ Generated {protocol} to {target} template:\n\n```json\n{json.dumps(template, indent=2)}\n```"


def generate_source_template(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate source configuration template

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing source configuration
    """
    base_config = {
        f"{protocol}-SOURCE": {
            "Name": f"{protocol}Source",
            "ProtocolAdapter": protocol,
            "Description": f"{protocol} source configuration",
            "Channels": {},
        }
    }

    return base_config


def generate_target_template(
    target: str, environment: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate target configuration template

    Args:
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        environment: Environment type (development, production)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing target configuration
    """
    base_config = {f"{target}Target": {"Active": True, "TargetType": target}}

    return base_config


def generate_target_types(target: str, sfc_knowledge: Dict[str, Any]) -> Dict[str, Any]:
    """Generate target types configuration

    Args:
        target: Target service (e.g., AWS-S3, AWS-IOT-CORE, DEBUG)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing target type configuration
    """
    target_types = {}

    # AWS targets
    if target == "AWS-S3":
        target_types["AWS-S3"] = {
            "JarFiles": ["${MODULES_DIR}/aws-s3-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awss3.AwsS3TargetWriter",
        }
    elif target == "AWS-IOT-CORE":
        target_types["AWS-IOT-CORE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-iot-core-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsiotcore.AwsIotCoreTargetWriter",
        }
    elif target == "AWS-IOT-ANALYTICS":
        target_types["AWS-IOT-ANALYTICS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-iot-analytics-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsiotanalytics.AwsIotAnalyticsTargetWriter",
        }
    elif target == "AWS-KINESIS":
        target_types["AWS-KINESIS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-kinesis-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awskinesis.AwsKinesisTargetWriter",
        }
    elif target == "AWS-KINESIS-FIREHOSE":
        target_types["AWS-KINESIS-FIREHOSE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-kinesis-firehose-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awskinesisfirehose.AwsKinesisFirehoseTargetWriter",
        }
    elif target == "AWS-S3-TABLES":
        target_types["AWS-S3-TABLES"] = {
            "JarFiles": ["${MODULES_DIR}/aws-s3-tables-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awss3tables.AwsS3TablesTargetWriter",
        }
    elif target == "AWS-LAMBDA":
        target_types["AWS-LAMBDA"] = {
            "JarFiles": ["${MODULES_DIR}/aws-lambda-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awslambda.AwsLambdaTargetWriter",
        }
    elif target == "AWS-MSK":
        target_types["AWS-MSK"] = {
            "JarFiles": ["${MODULES_DIR}/aws-msk-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awsmsk.AwsMskTargetWriter",
        }
    elif target == "AWS-SITEWISE":
        target_types["AWS-SITEWISE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sitewise-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssitewise.AwsSitewiseTargetWriter",
        }
    elif target == "AWS-SITEWISEEDGE":
        target_types["AWS-SITEWISEEDGE"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sitewise-edge-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssitewiseedge.AwsSitewiseEdgeTargetWriter",
        }
    elif target == "AWS-SNS":
        target_types["AWS-SNS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sns-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssns.AwsSnsTargetWriter",
        }
    elif target == "AWS-SQS":
        target_types["AWS-SQS"] = {
            "JarFiles": ["${MODULES_DIR}/aws-sqs-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awssqs.AwsSqsTargetWriter",
        }
    elif target == "AWS-TIMESTREAM":
        target_types["AWS-TIMESTREAM"] = {
            "JarFiles": ["${MODULES_DIR}/aws-timestream-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.awstimestream.AwsTimestreamTargetWriter",
        }

    # Edge targets
    elif target == "DEBUG":
        target_types["DEBUG-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/debug-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.debugtarget.DebugTargetWriter",
        }
    elif target == "FILE":
        target_types["FILE-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/file-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.filetarget.FileTargetWriter",
        }
    elif target == "MQTT":
        target_types["MQTT-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/mqtt-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.mqtt.MqttTargetWriter",
        }
    elif target == "NATS":
        target_types["NATS-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/nats-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.nats.NatsTargetWriter",
        }
    elif target == "OPCUA":
        target_types["OPCUA-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/opcua-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaTargetWriter",
        }
    elif target == "OPCUA-WRITER":
        target_types["OPCUA-WRITER"] = {
            "JarFiles": ["${MODULES_DIR}/opcua-writer/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaWriter",
        }
    elif target == "ROUTER":
        target_types["ROUTER-TARGET"] = {
            "JarFiles": ["${MODULES_DIR}/router-target/lib"],
            "FactoryClassName": "com.amazonaws.sfc.router.RouterTargetWriter",
        }

    return target_types


def generate_adapter_types(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate adapter types configuration

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing adapter type configuration
    """
    adapter_types = {}

    if protocol == "OPCUA":
        adapter_types["OPCUA"] = {
            "JarFiles": ["${MODULES_DIR}/opcua/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcua.OpcuaAdapter",
        }
    elif protocol == "MODBUS":
        adapter_types["MODBUS"] = {
            "JarFiles": ["${MODULES_DIR}/modbus/lib"],
            "FactoryClassName": "com.amazonaws.sfc.modbus.ModbusAdapter",
        }
    elif protocol == "S7":
        adapter_types["S7"] = {
            "JarFiles": ["${MODULES_DIR}/s7/lib"],
            "FactoryClassName": "com.amazonaws.sfc.s7.S7Adapter",
        }
    elif protocol == "ADS":
        adapter_types["ADS"] = {
            "JarFiles": ["${MODULES_DIR}/ads/lib"],
            "FactoryClassName": "com.amazonaws.sfc.ads.AdsAdapter",
        }
    elif protocol == "J1939":
        adapter_types["J1939"] = {
            "JarFiles": ["${MODULES_DIR}/j1939/lib"],
            "FactoryClassName": "com.amazonaws.sfc.j1939.J1939Adapter",
        }
    elif protocol == "MQTT":
        adapter_types["MQTT"] = {
            "JarFiles": ["${MODULES_DIR}/mqtt/lib"],
            "FactoryClassName": "com.amazonaws.sfc.mqtt.MqttAdapter",
        }
    elif protocol == "NATS":
        adapter_types["NATS"] = {
            "JarFiles": ["${MODULES_DIR}/nats/lib"],
            "FactoryClassName": "com.amazonaws.sfc.nats.NatsAdapter",
        }
    elif protocol == "OPCDA":
        adapter_types["OPCDA"] = {
            "JarFiles": ["${MODULES_DIR}/opcda/lib"],
            "FactoryClassName": "com.amazonaws.sfc.opcda.OpcdaAdapter",
        }
    elif protocol == "PCCC":
        adapter_types["PCCC"] = {
            "JarFiles": ["${MODULES_DIR}/pccc/lib"],
            "FactoryClassName": "com.amazonaws.sfc.pccc.PcccAdapter",
        }
    elif protocol == "REST":
        adapter_types["REST"] = {
            "JarFiles": ["${MODULES_DIR}/rest/lib"],
            "FactoryClassName": "com.amazonaws.sfc.rest.RestAdapter",
        }
    elif protocol == "SIMULATOR":
        adapter_types["SIMULATOR"] = {
            "JarFiles": ["${MODULES_DIR}/simulator/lib"],
            "FactoryClassName": "com.amazonaws.sfc.simulator.SimulatorAdapter",
        }
    elif protocol == "SLMP":
        adapter_types["SLMP"] = {
            "JarFiles": ["${MODULES_DIR}/slmp/lib"],
            "FactoryClassName": "com.amazonaws.sfc.slmp.SlmpAdapter",
        }
    elif protocol == "SNMP":
        adapter_types["SNMP"] = {
            "JarFiles": ["${MODULES_DIR}/snmp/lib"],
            "FactoryClassName": "com.amazonaws.sfc.snmp.SnmpAdapter",
        }
    elif protocol == "SQL":
        adapter_types["SQL"] = {
            "JarFiles": ["${MODULES_DIR}/sql/lib"],
            "FactoryClassName": "com.amazonaws.sfc.sql.SqlAdapter",
        }

    return adapter_types


def generate_protocol_adapter_config(
    protocol: str, sfc_knowledge: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate protocol adapter configuration

    Args:
        protocol: Source protocol (e.g., OPCUA, MODBUS, S7)
        sfc_knowledge: Dictionary containing SFC framework knowledge

    Returns:
        Dictionary containing protocol adapter configuration
    """
    config = {}

    return config
