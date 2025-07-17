syntax match vimbeRoleCodex /^codex$/
syntax match vimbeRoleCodexReasoning /^codex (reasoning)$/
syntax match vimbeRoleUser /^user$/
syntax match vimbeRoleError /^ERROR$/
syntax match vimbeRoleCommand /^command (.*)$/

hi link vimbeRoleCodex GruvboxGreenBold
hi link vimbeRoleCodexReasoning GruvboxGreen
hi link vimbeRoleUser GruvboxPurpleBold
hi link vimbeRoleError GruvboxRedBold
hi link vimbeRoleCommand GruvboxYellow
