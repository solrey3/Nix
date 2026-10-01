-- Keymaps are automatically loaded on the VeryLazy event.

-- Notes repository workflow. NOTES_REPO_PATH takes precedence; otherwise use
-- whichever of ~/Notes and ~/notes exists.
local function notes_root()
  local candidates = {
    vim.env.NOTES_REPO_PATH,
    "~/Notes",
    "~/notes",
  }

  for _, candidate in ipairs(candidates) do
    if candidate and candidate ~= "" then
      local path = vim.fn.expand(candidate)
      if vim.fn.isdirectory(path) == 1 then
        return vim.fs.normalize(path)
      end
    end
  end

  vim.notify(
    "Notes repository not found (set NOTES_REPO_PATH or create ~/Notes or ~/notes)",
    vim.log.levels.ERROR
  )
end

local function uuid()
  if vim.fn.executable("uuidgen") == 1 then
    return vim.trim(vim.fn.system("uuidgen"))
  end

  -- Portable fallback for hosts without uuidgen.
  local hash = vim.fn.sha256(('%s:%s:%s'):format(os.time(), vim.uv.hrtime(), math.random()))
  return ('%s-%s-4%s-a%s-%s'):format(
    hash:sub(1, 8),
    hash:sub(9, 12),
    hash:sub(14, 16),
    hash:sub(18, 20),
    hash:sub(21, 32)
  )
end

local function render_template(content, variables)
  variables = vim.tbl_extend("force", {
    date = os.date("%Y-%m-%d"),
    time = os.date("%H:%M:%S"),
    datetime = os.date("%Y%m%d%H%M%S"),
    uuid = uuid(),
  }, variables or {})

  return (content:gsub("{{(.-)}}", function(key)
    return variables[key] or "{{" .. key .. "}}"
  end))
end

local function create_note_with_template()
  local root = notes_root()
  if not root then
    return
  end

  local template_dir = root .. "/05-templates"
  local inbox_dir = root .. "/00-inbox"
  local templates = vim.fn.globpath(template_dir, "*.md", false, true)

  if #templates == 0 then
    vim.notify("No templates found in " .. template_dir, vim.log.levels.WARN)
    return
  end

  vim.ui.select(templates, {
    prompt = "Choose a note template:",
    format_item = function(path)
      return vim.fn.fnamemodify(path, ":t:r")
    end,
  }, function(template)
    if not template then
      return
    end

    local datetime = os.date("%Y%m%d%H%M%S")
    local filename = inbox_dir .. "/" .. datetime .. ".md"
    vim.cmd.edit(vim.fn.fnameescape(filename))

    local content = table.concat(vim.fn.readfile(template), "\n")
    local rendered = render_template(content, { title = datetime })
    vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(rendered, "\n", { plain = true }))
    vim.notify("Created note with " .. vim.fn.fnamemodify(template, ":t:r") .. " template")
  end)
end

local function save_and_rename_note()
  local bufnr = vim.api.nvim_get_current_buf()
  local current_path = vim.api.nvim_buf_get_name(bufnr)
  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  local title, created, date_value

  -- Locate the frontmatter block (first "---" to the next "---").
  local fm_end
  if lines[1] and lines[1]:match("^%-%-%-%s*$") then
    for i = 2, #lines do
      if lines[i]:match("^%-%-%-%s*$") then
        fm_end = i
        break
      end
    end
  end

  if fm_end then
    for i = 2, fm_end - 1 do
      local key, value = lines[i]:match("^(%w+):%s*(.-)%s*$")
      if key == "title" then
        title = value
      elseif key == "created" then
        created = value
      elseif key == "date" then
        date_value = value
      end
    end
  end

  -- New notes use the first H1 as their title (frontmatter title is legacy),
  -- so fall back to the first H1 when no title field is present.
  if not title then
    for i = (fm_end or 0) + 1, #lines do
      if lines[i]:match("^#%s") then
        title = lines[i]:gsub("^#%s*", "")
        break
      end
    end
  end

  -- Strip surrounding quotes from YAML string values.
  if title then
    title = title:gsub("^[\"']", ""):gsub("[\"']$", "")
  end

  -- Filename date comes from `created` (YYYY-MM-DD HH:MM:SS),
  -- falling back to the legacy `date` (YYYY-MM-DD).
  local raw_date = created or date_value
  local date = raw_date and raw_date:match("^(%d%d%d%d%-%d%d%-%d%d)")

  if not title or title == "" or not date then
    vim.notify(
      "A title (H1 or frontmatter) and a created/date field are required",
      vim.log.levels.ERROR
    )
    return
  end

  local slug = title:gsub("[^%w%s-]", ""):gsub("%s+", "-"):lower()
  local new_path = vim.fs.dirname(current_path) .. "/" .. date .. "-" .. slug .. ".md"
  current_path = vim.fs.normalize(current_path)
  new_path = vim.fs.normalize(new_path)

  if new_path == current_path then
    vim.cmd.write()
    return
  end

  if vim.uv.fs_stat(new_path) then
    vim.notify("A note already exists at " .. new_path, vim.log.levels.ERROR)
    return
  end

  local old_exists = vim.uv.fs_stat(current_path) ~= nil
  local renamed, rename_error = pcall(vim.api.nvim_buf_set_name, bufnr, new_path)
  if not renamed then
    vim.notify("Could not rename note: " .. rename_error, vim.log.levels.ERROR)
    return
  end

  local written, write_error = pcall(vim.cmd.write)
  if not written then
    pcall(vim.api.nvim_buf_set_name, bufnr, current_path)
    vim.notify("Could not save renamed note: " .. write_error, vim.log.levels.ERROR)
    return
  end

  if old_exists then
    local deleted = vim.fn.delete(current_path)
    if deleted ~= 0 then
      vim.notify("Saved renamed note, but could not remove " .. current_path, vim.log.levels.WARN)
      return
    end
  end

  vim.notify("Saved note as " .. vim.fs.basename(new_path))
end

vim.keymap.set("n", "<leader>on", create_note_with_template, { desc = "New Note from Template" })
vim.keymap.set("n", "<leader>ob", save_and_rename_note, { desc = "Save and Rename Note" })
vim.keymap.set("i", "<C-t>", function()
  vim.api.nvim_put({ os.date("%Y%m%d%H%M%S") }, "c", true, true)
end, { desc = "Insert Timestamp" })
