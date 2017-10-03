// Copyright 2017 Google Inc. All rights reserved.

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package drivers

import (
	"os"
	"testing"

	"github.com/GoogleCloudPlatform/runtimes-common/structure_tests/types/unversioned"
)

type Driver interface {
	Setup(t *testing.T, envVars []unversioned.EnvVar, fullCommand []unversioned.Command)

	// given an array of command parts, construct a full command and execute it against the
	// current environment. a list of environment variables can be passed to be set in the
	// environment before the command is executed. additionally, a boolean flag is passed
	// to specify whether or not we care about the output of the command.
	ProcessCommand(t *testing.T, envVars []unversioned.EnvVar, fullCommand []string) (string, string, int)

	StatFile(t *testing.T, path string) (os.FileInfo, error)

	ReadFile(t *testing.T, path string) ([]byte, error)

	ReadDir(t *testing.T, path string) ([]os.FileInfo, error)

	Destroy()
}

func InitDriverImpl(driver string) func(string) (Driver, error) {
	switch driver {
	// future drivers will be added here
	case "docker":
		return NewDockerDriver
	case "tar":
		return NewTarDriver
	default:
		return nil
	}
}